"""cria categorias de receita e receitas

Revision ID: ca423c3e46e3
Revises: 8b3f5a21c7d4
Create Date: 2026-11-10 21:29:48.057339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca423c3e46e3'
down_revision: Union[str, Sequence[str], None] = '8b3f5a21c7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Categorias que já vêm cadastradas (RF18)
CATEGORIAS_INICIAIS = [
    'Patrocínio',
    'Projetos e editais',
    'Doações',
]


def upgrade() -> None:
    """Upgrade schema."""
    categorias = op.create_table('categorias_receita',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=60), nullable=False),
    sa.Column('ativo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_categorias_receita'))
    )
    op.create_index('uq_categorias_receita_nome', 'categorias_receita', [sa.literal_column('lower(nome)')], unique=True)

    op.create_table('receitas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('data_receita', sa.Date(), nullable=False),
    sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('categoria_id', sa.Integer(), nullable=False),
    sa.Column('origem', sa.String(length=120), nullable=False),
    sa.Column('descricao', sa.String(length=255), nullable=True),
    sa.Column('criado_por_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('valor > 0', name=op.f('ck_receitas_valor_positivo')),
    sa.ForeignKeyConstraint(['categoria_id'], ['categorias_receita.id'], name=op.f('fk_receitas_categoria_id_categorias_receita')),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], name=op.f('fk_receitas_criado_por_id_usuarios')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_receitas'))
    )
    op.create_index(op.f('ix_receitas_categoria_id'), 'receitas', ['categoria_id'], unique=False)
    op.create_index(op.f('ix_receitas_data_receita'), 'receitas', ['data_receita'], unique=False)

    op.bulk_insert(categorias, [{'nome': nome} for nome in CATEGORIAS_INICIAIS])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_receitas_data_receita'), table_name='receitas')
    op.drop_index(op.f('ix_receitas_categoria_id'), table_name='receitas')
    op.drop_table('receitas')
    op.drop_index('uq_categorias_receita_nome', table_name='categorias_receita')
    op.drop_table('categorias_receita')
