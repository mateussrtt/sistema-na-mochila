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
from app.models.usuario import Usuario


class FormaDePagamento(enum.StrEnum):
    """Como o dinheiro chegou. O sistema só registra: não há ligação com banco."""

    PIX = "pix"
    DINHEIRO = "dinheiro"
    BOLETO = "boleto"
    OUTRA = "outra"


class Pagamento(Base):
    __tablename__ = "pagamentos"
    __table_args__ = (
        # Uma mensalidade só aceita um pagamento ativo (RF10). Um pagamento cancelado, no futuro
        # (RF17), deixa de contar e a mensalidade pode receber outro
        Index(
            "uq_pagamentos_mensalidade_ativo",
            "mensalidade_id",
            unique=True,
            postgresql_where=text("cancelado_em IS NULL"),
        ),
        # RN09: todo lançamento tem valor maior que zero
        CheckConstraint("valor_pago > 0", name="valor_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mensalidade_id: Mapped[int] = mapped_column(ForeignKey("mensalidades.id"), index=True)
    # Dia em que o dinheiro entrou (regime de caixa, RN10). RN09: não pode ser no futuro
    data_pagamento: Mapped[date]
    valor_pago: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    forma_pagamento: Mapped[FormaDePagamento] = mapped_column(
        Enum(
            FormaDePagamento,
            name="forma_pagamento",
            native_enum=False,
            length=10,
            create_constraint=True,
            values_callable=lambda formas: [f.value for f in formas],
        )
    )
    # Obrigatória quando o valor pago é diferente do valor da mensalidade
    observacao: Mapped[str | None] = mapped_column(String(255))
    # Quem registrou e quando (RF26)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Preenchido só quando o administrador cancelar o pagamento (RF17, issue futura)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    criado_por: Mapped[Usuario] = relationship()
