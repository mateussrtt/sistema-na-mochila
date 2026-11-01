"""adiciona isencao e cancelamento na mensalidade

Revision ID: cda6bedd41c4
Revises: d6850806fa93
Create Date: 2026-11-01 14:43:48.844135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cda6bedd41c4'
down_revision: Union[str, Sequence[str], None] = 'd6850806fa93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('mensalidades', sa.Column('motivo_alteracao', sa.String(length=255), nullable=True))
    op.add_column('mensalidades', sa.Column('alterado_por_id', sa.Integer(), nullable=True))
    op.add_column('mensalidades', sa.Column('alterado_em', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(op.f('fk_mensalidades_alterado_por_id_usuarios'), 'mensalidades', 'usuarios', ['alterado_por_id'], ['id'])
    # O autogenerate não enxerga CHECK: isenta ou cancelada exige motivo, autor e hora (RF14, RF26)
    op.create_check_constraint(
        op.f('ck_mensalidades_isenta_ou_cancelada_com_motivo'),
        'mensalidades',
        "status NOT IN ('isenta', 'cancelada') OR (motivo_alteracao IS NOT NULL AND alterado_por_id IS NOT NULL AND alterado_em IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ck_mensalidades_isenta_ou_cancelada_com_motivo'), 'mensalidades', type_='check')
    op.drop_constraint(op.f('fk_mensalidades_alterado_por_id_usuarios'), 'mensalidades', type_='foreignkey')
    op.drop_column('mensalidades', 'alterado_em')
    op.drop_column('mensalidades', 'alterado_por_id')
    op.drop_column('mensalidades', 'motivo_alteracao')
