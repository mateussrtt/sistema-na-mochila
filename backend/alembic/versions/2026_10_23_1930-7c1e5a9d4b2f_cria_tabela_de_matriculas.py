"""cria tabela de matriculas

Revision ID: 7c1e5a9d4b2f
Revises: 12f309b099e3
Create Date: 2026-10-23 19:30:12.318204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1e5a9d4b2f'
down_revision: Union[str, Sequence[str], None] = '12f309b099e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('matriculas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('aluno_id', sa.Integer(), nullable=False),
    sa.Column('data_inicio', sa.Date(), nullable=False),
    sa.Column('data_encerramento', sa.Date(), nullable=True),
    sa.Column('valor_mensalidade', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('situacao', sa.Enum('ativa', 'encerrada', name='situacao', native_enum=False, create_constraint=True, length=10), server_default='ativa', nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id'], name=op.f('fk_matriculas_aluno_id_alunos')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_matriculas'))
    )
    op.create_index(op.f('ix_matriculas_aluno_id'), 'matriculas', ['aluno_id'], unique=False)
    op.create_index('uq_matriculas_aluno_ativa', 'matriculas', ['aluno_id'], unique=True, postgresql_where=sa.text("situacao = 'ativa'"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_matriculas_aluno_ativa', table_name='matriculas', postgresql_where=sa.text("situacao = 'ativa'"))
    op.drop_index(op.f('ix_matriculas_aluno_id'), table_name='matriculas')
    op.drop_table('matriculas')
