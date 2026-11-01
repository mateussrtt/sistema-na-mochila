"""cria tabela de pagamentos

Revision ID: d6850806fa93
Revises: b924f6de7708
Create Date: 2026-11-01 12:26:40.715879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6850806fa93'
down_revision: Union[str, Sequence[str], None] = 'b924f6de7708'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pagamentos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mensalidade_id', sa.Integer(), nullable=False),
    sa.Column('data_pagamento', sa.Date(), nullable=False),
    sa.Column('valor_pago', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('forma_pagamento', sa.Enum('pix', 'dinheiro', 'boleto', 'outra', name='forma_pagamento', native_enum=False, create_constraint=True, length=10), nullable=False),
    sa.Column('observacao', sa.String(length=255), nullable=True),
    sa.Column('criado_por_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('cancelado_em', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('valor_pago > 0', name=op.f('ck_pagamentos_valor_positivo')),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], name=op.f('fk_pagamentos_criado_por_id_usuarios')),
    sa.ForeignKeyConstraint(['mensalidade_id'], ['mensalidades.id'], name=op.f('fk_pagamentos_mensalidade_id_mensalidades')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pagamentos'))
    )
    op.create_index(op.f('ix_pagamentos_mensalidade_id'), 'pagamentos', ['mensalidade_id'], unique=False)
    op.create_index('uq_pagamentos_mensalidade_ativo', 'pagamentos', ['mensalidade_id'], unique=True, postgresql_where=sa.text('cancelado_em IS NULL'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_pagamentos_mensalidade_ativo', table_name='pagamentos', postgresql_where=sa.text('cancelado_em IS NULL'))
    op.drop_index(op.f('ix_pagamentos_mensalidade_id'), table_name='pagamentos')
    op.drop_table('pagamentos')
