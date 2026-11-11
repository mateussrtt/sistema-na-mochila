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

    categoria: Mapped[CategoriaReceita] = relationship()
    criado_por: Mapped[Usuario] = relationship()
