from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.usuario import Usuario


class CategoriaReceita(Base):
    """De onde o dinheiro vem: patrocínio, projetos e editais, doações... (RF18).

    Mensalidades e cobranças das empresas padrinhas não são categorias de receita: elas têm
    tabelas próprias e entram no caixa por lá, para não contar o mesmo dinheiro duas vezes.

    A lista é cadastrável. Uma categoria inativa não recebe receitas novas, mas as que já foram
    lançadas nela continuam no histórico. Nada é apagado (RN12).
    """

    __tablename__ = "categorias_receita"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(60))
    ativo: Mapped[bool] = mapped_column(server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Duas categorias com o mesmo nome (sem diferenciar maiúsculas de minúsculas) só atrapalhariam
# quem lança a receita
Index("uq_categorias_receita_nome", func.lower(CategoriaReceita.nome), unique=True)


class Receita(Base):
    """Dinheiro que entrou na associação além das mensalidades (RF18).

    Toda receita tem categoria e origem (RN08).
    """

    __tablename__ = "receitas"
    __table_args__ = (
        # RN09: todo lançamento tem valor maior que zero
        CheckConstraint("valor > 0", name="valor_positivo"),
        # Cancelar exige o motivo, quem fez e quando, tudo junto (RF17, RF26, RN12)
        CheckConstraint(
            "(cancelado_em IS NULL AND motivo_cancelamento IS NULL AND cancelado_por_id IS NULL)"
            " OR (cancelado_em IS NOT NULL AND motivo_cancelamento IS NOT NULL"
            " AND cancelado_por_id IS NOT NULL)",
            name="cancelamento_completo",
        ),
        # Um lançamento cancelado é corrigido no máximo uma vez
        UniqueConstraint("substitui_id", name="uq_receitas_substitui_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dia em que o dinheiro entrou (regime de caixa, RN10). RN09: não pode ser no futuro
    data_receita: Mapped[date] = mapped_column(index=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias_receita.id"), index=True)
    # Quem pagou: o patrocinador, o edital, quem doou (RN08)
    origem: Mapped[str] = mapped_column(String(120))
    # Detalhe opcional, como o nome do projeto ou do evento
    descricao: Mapped[str | None] = mapped_column(String(255))
    # Quem registrou e quando (RF26)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Preenchidos só quando o administrador cancela o lançamento (RF17). Nada é apagado (RN12)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    cancelado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    # Na correção, o lançamento novo aponta para o que ele substitui (RF17)
    substitui_id: Mapped[int | None] = mapped_column(ForeignKey("receitas.id"))

    categoria: Mapped[CategoriaReceita] = relationship()
    criado_por: Mapped[Usuario] = relationship(foreign_keys=[criado_por_id])
    cancelado_por: Mapped[Usuario | None] = relationship(foreign_keys=[cancelado_por_id])
