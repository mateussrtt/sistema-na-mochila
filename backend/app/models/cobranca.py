import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mensalidade import Mensalidade
from app.models.padrinho import Padrinho
from app.models.usuario import Usuario


class StatusCobranca(enum.StrEnum):
    """O que fica guardado no banco. "A vencer" e "atrasada" não são guardadas: são calculadas."""

    A_EMITIR = "a_emitir"
    EMITIDA = "emitida"
    PAGA = "paga"
    CANCELADA = "cancelada"


class SituacaoCobranca(enum.StrEnum):
    """A situação que a pessoa vê na tela (RF31)."""

    A_EMITIR = "a_emitir"
    A_VENCER = "a_vencer"
    ATRASADA = "atrasada"
    PAGA = "paga"
    CANCELADA = "cancelada"


class FormaDePagamentoCobranca(enum.StrEnum):
    """Como a empresa pagou. O sistema só registra: não há ligação com banco."""

    PIX = "pix"
    TRANSFERENCIA = "transferencia"
    BOLETO = "boleto"
    OUTRA = "outra"


def situacao_da_cobranca(
    status: StatusCobranca, data_vencimento: date, hoje: date
) -> SituacaoCobranca:
    """Só a cobrança com nota emitida pode atrasar: do dia seguinte ao vencimento em diante (RN07).

    A cobrança "a emitir" ainda não tem vencimento confirmado; se a nota passou do prazo da
    empresa, isso aparece à parte, em `emissao_atrasada`.
    """
    if status == StatusCobranca.EMITIDA:
        if hoje > data_vencimento:
            return SituacaoCobranca.ATRASADA
        return SituacaoCobranca.A_VENCER
    return SituacaoCobranca(status.value)


def emissao_atrasada(status: StatusCobranca, limite_emissao: date | None, hoje: date) -> bool:
    """A nota ainda não foi emitida e o prazo combinado com a empresa já passou."""
    return (
        status == StatusCobranca.A_EMITIR and limite_emissao is not None and hoje > limite_emissao
    )


class Cobranca(Base):
    """O que uma empresa padrinha deve em um mês: a soma das mensalidades dos alunos dela (RN18).

    A nota fiscal é emitida fora do sistema; aqui se registra o número, as datas e o pagamento.
    """

    __tablename__ = "cobrancas"
    __table_args__ = (
        # Uma cobrança aberta por empresa e mês: o aluno que entra depois cai nela. Depois que a
        # nota é emitida, quem entrar ainda naquele mês forma uma cobrança complementar
        Index(
            "uq_cobrancas_padrinho_competencia_a_emitir",
            "padrinho_id",
            "competencia",
            unique=True,
            postgresql_where=text("status = 'a_emitir'"),
        ),
        CheckConstraint("valor > 0", name="valor_positivo"),
        # A competência é sempre o primeiro dia do mês de referência
        CheckConstraint("EXTRACT(day FROM competencia) = 1", name="competencia_dia_um"),
        CheckConstraint("data_vencimento >= competencia", name="vencimento_depois_da_competencia"),
        CheckConstraint(
            "limite_emissao IS NULL OR limite_emissao >= competencia",
            name="limite_depois_da_competencia",
        ),
        CheckConstraint(
            "data_emissao IS NULL OR data_vencimento >= data_emissao",
            name="vencimento_depois_da_emissao",
        ),
        # Antes de emitir não há nota; emitida e paga têm o número, a data e quem registrou (RF26)
        CheckConstraint(
            "status <> 'a_emitir' OR (numero_nota IS NULL AND data_emissao IS NULL)",
            name="a_emitir_sem_nota",
        ),
        CheckConstraint(
            "status NOT IN ('emitida', 'paga') OR (numero_nota IS NOT NULL "
            "AND data_emissao IS NOT NULL AND emitida_por_id IS NOT NULL "
            "AND emitida_em IS NOT NULL)",
            name="emitida_com_nota",
        ),
        # Cancelar exige o motivo, quem fez e quando (RF26, RN12)
        CheckConstraint(
            "status <> 'cancelada' OR (motivo_cancelamento IS NOT NULL "
            "AND cancelado_por_id IS NOT NULL AND cancelado_em IS NOT NULL)",
            name="cancelada_com_motivo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    padrinho_id: Mapped[int] = mapped_column(ForeignKey("padrinhos.id"), index=True)
    competencia: Mapped[date] = mapped_column(index=True)
    # Soma das mensalidades dos alunos da cobrança no momento em que a nota é emitida
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[StatusCobranca] = mapped_column(
        Enum(
            StatusCobranca,
            name="status",
            native_enum=False,
            length=10,
            create_constraint=True,
            values_callable=lambda status: [s.value for s in status],
        ),
        default=StatusCobranca.A_EMITIR,
        server_default=StatusCobranca.A_EMITIR.value,
    )
    # Sugerido pelo dia combinado com a empresa; quem registra a nota confirma ou corrige
    data_vencimento: Mapped[date]
    # Prazo para emitir a nota, copiado do que estava combinado quando a cobrança nasceu
    limite_emissao: Mapped[date | None]

    numero_nota: Mapped[str | None] = mapped_column(String(30))
    data_emissao: Mapped[date | None]
    emitida_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    emitida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Quem gerou e quando (RF26)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Preenchidos só quando o administrador cancela. Nada é apagado (RN12)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    cancelado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    padrinho: Mapped[Padrinho] = relationship()
    criado_por: Mapped[Usuario] = relationship(foreign_keys=[criado_por_id])
    emitida_por: Mapped[Usuario | None] = relationship(foreign_keys=[emitida_por_id])
    cancelado_por: Mapped[Usuario | None] = relationship(foreign_keys=[cancelado_por_id])
    mensalidades: Mapped[list[Mensalidade]] = relationship(order_by=Mensalidade.id)


# Dois números de nota iguais seriam, quase certamente, um erro de digitação (sem diferenciar
# maiúsculas de minúsculas)
Index("uq_cobrancas_numero_nota", func.lower(Cobranca.numero_nota), unique=True)


class PagamentoCobranca(Base):
    """O pagamento que a empresa fez de uma cobrança (RF31)."""

    __tablename__ = "pagamentos_cobranca"
    __table_args__ = (
        # Uma cobrança só aceita um pagamento ativo. Um pagamento cancelado (RF17) deixa de
        # contar e a cobrança pode receber outro
        Index(
            "uq_pagamentos_cobranca_ativo",
            "cobranca_id",
            unique=True,
            postgresql_where=text("cancelado_em IS NULL"),
        ),
        # RN09: todo lançamento tem valor maior que zero
        CheckConstraint("valor_pago > 0", name="valor_positivo"),
        # Cancelar exige o motivo, quem fez e quando, tudo junto (RF17, RF26, RN12)
        CheckConstraint(
            "(cancelado_em IS NULL AND motivo_cancelamento IS NULL AND cancelado_por_id IS NULL)"
            " OR (cancelado_em IS NOT NULL AND motivo_cancelamento IS NOT NULL"
            " AND cancelado_por_id IS NOT NULL)",
            name="cancelamento_completo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cobranca_id: Mapped[int] = mapped_column(ForeignKey("cobrancas.id"), index=True)
    # Dia em que o dinheiro entrou (regime de caixa, RN10). RN09: não pode ser no futuro
    data_pagamento: Mapped[date]
    valor_pago: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    forma_pagamento: Mapped[FormaDePagamentoCobranca] = mapped_column(
        Enum(
            FormaDePagamentoCobranca,
            name="forma_pagamento_cobranca",
            native_enum=False,
            length=15,
            create_constraint=True,
            values_callable=lambda formas: [f.value for f in formas],
        )
    )
    # Obrigatória quando o valor pago é diferente do valor da cobrança
    observacao: Mapped[str | None] = mapped_column(String(255))
    # Quem registrou e quando (RF26)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Preenchidos só quando o administrador cancela o lançamento (RF17). Nada é apagado (RN12)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    cancelado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    criado_por: Mapped[Usuario] = relationship(foreign_keys=[criado_por_id])
    cancelado_por: Mapped[Usuario | None] = relationship(foreign_keys=[cancelado_por_id])
