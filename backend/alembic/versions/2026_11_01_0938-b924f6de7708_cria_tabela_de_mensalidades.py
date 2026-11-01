"""cria tabela de mensalidades

Revision ID: b924f6de7708
Revises: c7316c6e60ab
Create Date: 2026-11-01 09:38:11.022144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b924f6de7708'
down_revision: Union[str, Sequence[str], None] = 'c7316c6e60ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mensalidades',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('matricula_id', sa.Integer(), nullable=False),
    sa.Column('competencia', sa.Date(), nullable=False),
    sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('data_vencimento', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('pendente', 'paga', 'isenta', 'cancelada', name='status', native_enum=False, create_constraint=True, length=10), server_default='pendente', nullable=False),
    sa.Column('criado_por_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('EXTRACT(day FROM competencia) = 1', name=op.f('ck_mensalidades_competencia_dia_um')),
    sa.CheckConstraint('data_vencimento >= competencia', name=op.f('ck_mensalidades_vencimento_depois_da_competencia')),
    sa.CheckConstraint('valor > 0', name=op.f('ck_mensalidades_valor_positivo')),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], name=op.f('fk_mensalidades_criado_por_id_usuarios')),
    sa.ForeignKeyConstraint(['matricula_id'], ['matriculas.id'], name=op.f('fk_mensalidades_matricula_id_matriculas')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_mensalidades')),
    sa.UniqueConstraint('matricula_id', 'competencia', name='uq_mensalidades_matricula_competencia')
    )
    op.create_index(op.f('ix_mensalidades_competencia'), 'mensalidades', ['competencia'], unique=False)
    op.create_index(op.f('ix_mensalidades_matricula_id'), 'mensalidades', ['matricula_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mensalidades_matricula_id'), table_name='mensalidades')
    op.drop_index(op.f('ix_mensalidades_competencia'), table_name='mensalidades')
    op.drop_table('mensalidades')
