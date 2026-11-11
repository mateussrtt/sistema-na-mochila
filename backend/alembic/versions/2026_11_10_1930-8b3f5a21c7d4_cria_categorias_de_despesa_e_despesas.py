"""cria categorias de despesa e despesas

Revision ID: 8b3f5a21c7d4
Revises: 4dae67b6e63e
Create Date: 2026-11-10 19:30:12.384512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b3f5a21c7d4'
down_revision: Union[str, Sequence[str], None] = '4dae67b6e63e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Categorias que já vêm cadastradas (RF15)
CATEGORIAS_INICIAIS = [
    'Kits de robótica',
    'Viagens',
    'Custos fixos',
    'Professores',
    'Peças',
    'Inscrições em competições',
]


def upgrade() -> None:
    """Upgrade schema."""
    categorias = op.create_table('categorias_despesa',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=60), nullable=False),
    sa.Column('ativo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_categorias_despesa'))
    )
    op.create_index('uq_categorias_despesa_nome', 'categorias_despesa', [sa.literal_column('lower(nome)')], unique=True)

    op.create_table('despesas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('data_despesa', sa.Date(), nullable=False),
    sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('categoria_id', sa.Integer(), nullable=False),
    sa.Column('descricao', sa.String(length=255), nullable=False),
    sa.Column('favorecido', sa.String(length=120), nullable=False),
    sa.Column('criado_por_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('valor > 0', name=op.f('ck_despesas_valor_positivo')),
    sa.ForeignKeyConstraint(['categoria_id'], ['categorias_despesa.id'], name=op.f('fk_despesas_categoria_id_categorias_despesa')),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], name=op.f('fk_despesas_criado_por_id_usuarios')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_despesas'))
    )
    op.create_index(op.f('ix_despesas_categoria_id'), 'despesas', ['categoria_id'], unique=False)
    op.create_index(op.f('ix_despesas_data_despesa'), 'despesas', ['data_despesa'], unique=False)

    op.bulk_insert(categorias, [{'nome': nome} for nome in CATEGORIAS_INICIAIS])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_despesas_data_despesa'), table_name='despesas')
    op.drop_index(op.f('ix_despesas_categoria_id'), table_name='despesas')
    op.drop_table('despesas')
    op.drop_index('uq_categorias_despesa_nome', table_name='categorias_despesa')
    op.drop_table('categorias_despesa')
