import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.matricula import Matricula

# RN06: a mensalidade vence no dia 10 de cada mês
DIA_DO_VENCIMENTO = 10


class StatusMensalidade(enum.StrEnum):
    """O que fica guardado no banco. "A vencer" e "atrasada" não são guardadas: são calculadas."""

    PENDENTE = "pendente"
    PAGA = "paga"
    ISENTA = "isenta"
    CANCELADA = "cancelada"


class SituacaoMensalidade(enum.StrEnum):
    """A situação que a pessoa vê na tela (RF11)."""

    A_VENCER = "a_vencer"
    ATRASADA = "atrasada"
    PAGA = "paga"
    ISENTA = "isenta"
    CANCELADA = "cancelada"


def situacao_da_mensalidade(
    status: StatusMensalidade, data_vencimento: date, hoje: date
) -> SituacaoMensalidade:
    """Até o dia do vencimento (inclusive) fica "a vencer"; do dia seguinte em diante, "atrasada".

    Só a mensalidade pendente pode atrasar. Paga, isenta e cancelada mostram o próprio status
    (RN07).
    """
    if status == StatusMensalidade.PENDENTE:
        if hoje > data_vencimento:
            return SituacaoMensalidade.ATRASADA
        return SituacaoMensalidade.A_VENCER
    return SituacaoMensalidade(status.value)


def data_de_vencimento(competencia: date, data_inicio: date) -> date:
    """Dia 10 do mês (RN06). Quem entra depois do dia 10 vence na própria data de início.

    Sem isso, a primeira mensalidade já nasceria atrasada no dia da matrícula.
    """
    return max(competencia.replace(day=DIA_DO_VENCIMENTO), data_inicio)


class Mensalidade(Base):
    __tablename__ = "mensalidades"
    __table_args__ = (
        # Cada matrícula tem uma mensalidade por mês: gerar de novo não duplica (RN05, RF09)
        UniqueConstraint(
            "matricula_id", "competencia", name="uq_mensalidades_matricula_competencia"
        ),
        # Matrícula com bolsa integral não gera mensalidade, então o valor é sempre positivo
        CheckConstraint("valor > 0", name="valor_positivo"),
        # A competência é sempre o primeiro dia do mês de referência
        CheckConstraint("EXTRACT(day FROM competencia) = 1", name="competencia_dia_um"),
        CheckConstraint("data_vencimento >= competencia", name="vencimento_depois_da_competencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    matricula_id: Mapped[int] = mapped_column(ForeignKey("matriculas.id"), index=True)
    competencia: Mapped[date] = mapped_column(index=True)
    # Cópia do valor da matrícula na hora da geração: o histórico não muda se a matrícula mudar
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    data_vencimento: Mapped[date]
    status: Mapped[StatusMensalidade] = mapped_column(
        Enum(
            StatusMensalidade,
            name="status",
            native_enum=False,
            length=10,
            create_constraint=True,
            values_callable=lambda status: [s.value for s in status],
        ),
        default=StatusMensalidade.PENDENTE,
        server_default=StatusMensalidade.PENDENTE.value,
    )
    # Quem gerou e quando (RF26)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    matricula: Mapped[Matricula] = relationship()
