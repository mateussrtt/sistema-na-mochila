from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.usuario import Usuario


class CategoriaDespesa(Base):
    """Para onde o dinheiro vai: kits, viagens, custos fixos... (RF15).

    A lista é cadastrável. Uma categoria inativa não recebe despesas novas, mas as que já foram
    lançadas nela continuam no histórico. Nada é apagado (RN12).
    """

    __tablename__ = "categorias_despesa"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(60))
    ativo: Mapped[bool] = mapped_column(server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Duas categorias com o mesmo nome (sem diferenciar maiúsculas de minúsculas) só atrapalhariam
# quem lança a despesa
Index("uq_categorias_despesa_nome", func.lower(CategoriaDespesa.nome), unique=True)


class Despesa(Base):
    """Dinheiro que saiu da associação (RF16). Toda despesa tem categoria (RN08)."""

    __tablename__ = "despesas"
    __table_args__ = (
        # RN09: todo lançamento tem valor maior que zero
        CheckConstraint("valor > 0", name="valor_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dia em que o dinheiro saiu (regime de caixa, RN10). RN09: não pode ser no futuro
    data_despesa: Mapped[date] = mapped_column(index=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias_despesa.id"), index=True)
    descricao: Mapped[str] = mapped_column(String(255))
    # Para quem foi pago: pessoa ou empresa
    favorecido: Mapped[str] = mapped_column(String(120))
    # Quem registrou e quando (RF26)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    categoria: Mapped[CategoriaDespesa] = relationship()
    criado_por: Mapped[Usuario] = relationship()
