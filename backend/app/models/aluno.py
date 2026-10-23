from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.responsavel import Responsavel

# Tabela de ligação: um aluno tem vários responsáveis e um responsável pode ter vários alunos
aluno_responsavel = Table(
    "aluno_responsavel",
    Base.metadata,
    Column("aluno_id", ForeignKey("alunos.id", ondelete="CASCADE"), primary_key=True),
    Column("responsavel_id", ForeignKey("responsaveis.id", ondelete="CASCADE"), primary_key=True),
)


class Aluno(Base):
    __tablename__ = "alunos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), index=True)
    data_nascimento: Mapped[date | None]
    escola: Mapped[str | None] = mapped_column(String(120))
    municipio: Mapped[str | None] = mapped_column(String(80))
    # Aluno inativo não é apagado, para não perder o histórico financeiro
    ativo: Mapped[bool] = mapped_column(server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    responsaveis: Mapped[list["Responsavel"]] = relationship(
        secondary=aluno_responsavel, back_populates="alunos", order_by="Responsavel.nome"
    )
