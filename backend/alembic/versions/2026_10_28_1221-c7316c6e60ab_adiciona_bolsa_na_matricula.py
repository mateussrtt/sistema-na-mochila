"""adiciona bolsa na matricula

Revision ID: c7316c6e60ab
Revises: 0dd5a07cc536
Create Date: 2026-10-28 12:21:09.019212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7316c6e60ab'
down_revision: Union[str, Sequence[str], None] = '0dd5a07cc536'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # As matrículas que já existem ficam "sem bolsa"
    op.add_column('matriculas', sa.Column('bolsa', sa.String(length=10), server_default='nenhuma', nullable=False))
    op.create_check_constraint(
        op.f('ck_matriculas_bolsa'), 'matriculas', "bolsa IN ('nenhuma', 'parcial', 'integral')"
    )
    op.create_check_constraint(
        op.f('ck_matriculas_valor_conforme_bolsa'),
        'matriculas',
        "(bolsa = 'integral' AND valor_mensalidade = 0)"
        " OR (bolsa <> 'integral' AND valor_mensalidade > 0)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ck_matriculas_valor_conforme_bolsa'), 'matriculas', type_='check')
    op.drop_constraint(op.f('ck_matriculas_bolsa'), 'matriculas', type_='check')
    op.drop_column('matriculas', 'bolsa')
