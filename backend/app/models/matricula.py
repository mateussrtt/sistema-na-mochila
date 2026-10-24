import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.aluno import Aluno


class SituacaoMatricula(enum.StrEnum):
    ATIVA = "ativa"
    ENCERRADA = "encerrada"


class Matricula(Base):
    __tablename__ = "matriculas"
    __table_args__ = (
        # Um aluno só pode ter uma matrícula ativa por vez, senão a mensalidade sairia em dobro
        Index(
            "uq_matriculas_aluno_ativa",
            "aluno_id",
            unique=True,
            postgresql_where=text("situacao = 'ativa'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey("alunos.id"), index=True)
    data_inicio: Mapped[date]
    # Preenchida ao encerrar. A matrícula não é apagada, para manter o histórico financeiro
    data_encerramento: Mapped[date | None]
    # O valor é definido em cada matrícula, então alunos diferentes podem pagar valores diferentes
    valor_mensalidade: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    situacao: Mapped[SituacaoMatricula] = mapped_column(
        Enum(
            SituacaoMatricula,
            name="situacao",
            native_enum=False,
            length=10,
            create_constraint=True,
            values_callable=lambda situacoes: [s.value for s in situacoes],
        ),
        default=SituacaoMatricula.ATIVA,
        server_default=SituacaoMatricula.ATIVA.value,
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    aluno: Mapped[Aluno] = relationship()
