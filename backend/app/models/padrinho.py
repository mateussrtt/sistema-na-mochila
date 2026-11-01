from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Padrinho(Base):
    """Empresa que paga as mensalidades de alunos apadrinhados (RF29).

    O vencimento é combinado com cada empresa: `dia_vencimento` é o dia do mês em que a cobrança
    vence e `emitir_ate_dia`, se houver, o dia até o qual a nota deve ser emitida. O sistema só
    registra: a nota fiscal é emitida fora dele.
    """

    __tablename__ = "padrinhos"
    __table_args__ = (
        # Dia 28 é o último que existe em todos os meses
        CheckConstraint("dia_vencimento BETWEEN 1 AND 28", name="dia_vencimento_de_1_a_28"),
        # A nota se emite antes do vencimento (ou no próprio dia), nunca depois
        CheckConstraint(
            "emitir_ate_dia IS NULL OR (emitir_ate_dia BETWEEN 1 AND 28"
            " AND emitir_ate_dia <= dia_vencimento)",
            name="emitir_ate_dia_valido",
        ),
        # 12 letras ou números e 2 dígitos verificadores (CNPJ numérico ou alfanumérico)
        CheckConstraint("cnpj IS NULL OR cnpj ~ '^[0-9A-Z]{12}[0-9]{2}$'", name="cnpj_formato"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), index=True)
    # Só os 14 caracteres, sem máscara. Opcional, mas não pode repetir (NULL não conta como igual)
    cnpj: Mapped[str | None] = mapped_column(String(14), unique=True)
    # Pessoa da empresa que combina e recebe a cobrança
    contato: Mapped[str | None] = mapped_column(String(120))
    # Telefone e e-mail são obrigatórios: é por eles que se fala com a empresa sobre a cobrança
    telefone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(254))
    dia_vencimento: Mapped[int] = mapped_column(SmallInteger)
    emitir_ate_dia: Mapped[int | None] = mapped_column(SmallInteger)
    # Padrinho inativo não é apagado, para não perder o histórico
    ativo: Mapped[bool] = mapped_column(server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
