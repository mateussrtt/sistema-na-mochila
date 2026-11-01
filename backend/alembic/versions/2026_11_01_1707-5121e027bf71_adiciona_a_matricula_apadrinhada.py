"""adiciona a matricula apadrinhada

Revision ID: 5121e027bf71
Revises: 91e9466147f9
Create Date: 2026-11-01 17:07:55.488268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5121e027bf71'
down_revision: Union[str, Sequence[str], None] = '91e9466147f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # O autogenerate não enxerga mudança em CHECK: a da bolsa e a nova regra são escritas à mão.
    # "apadrinhada" tem 11 letras e a coluna tinha 10: ela precisa ser alargada antes.
    op.drop_constraint(op.f('ck_matriculas_bolsa'), 'matriculas', type_='check')
    op.alter_column('matriculas', 'bolsa',
               existing_type=sa.VARCHAR(length=10),
               type_=sa.String(length=15),
               existing_nullable=False,
               existing_server_default=sa.text("'nenhuma'::character varying"))
    op.create_check_constraint(
        op.f('ck_matriculas_bolsa'),
        'matriculas',
        "bolsa IN ('nenhuma', 'parcial', 'integral', 'apadrinhada')",
    )
    op.add_column('matriculas', sa.Column('padrinho_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_matriculas_padrinho_id'), 'matriculas', ['padrinho_id'], unique=False)
    op.create_foreign_key(op.f('fk_matriculas_padrinho_id_padrinhos'), 'matriculas', 'padrinhos', ['padrinho_id'], ['id'])
    # Só a matrícula apadrinhada tem padrinho, e toda matrícula apadrinhada tem um
    op.create_check_constraint(
        op.f('ck_matriculas_padrinho_conforme_bolsa'),
        'matriculas',
        "(bolsa = 'apadrinhada') = (padrinho_id IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ck_matriculas_padrinho_conforme_bolsa'), 'matriculas', type_='check')
    # Voltar para antes da bolsa apadrinhada: quem foi apadrinhado passa a "sem bolsa", mantendo o
    # valor da mensalidade (o apadrinhamento em si se perde junto com a coluna do padrinho)
    op.execute("UPDATE matriculas SET bolsa = 'nenhuma' WHERE bolsa = 'apadrinhada'")
    op.drop_constraint(op.f('fk_matriculas_padrinho_id_padrinhos'), 'matriculas', type_='foreignkey')
    op.drop_index(op.f('ix_matriculas_padrinho_id'), table_name='matriculas')
    op.drop_column('matriculas', 'padrinho_id')
    op.drop_constraint(op.f('ck_matriculas_bolsa'), 'matriculas', type_='check')
    op.alter_column('matriculas', 'bolsa',
               existing_type=sa.String(length=15),
               type_=sa.VARCHAR(length=10),
               existing_nullable=False,
               existing_server_default=sa.text("'nenhuma'::character varying"))
    op.create_check_constraint(
        op.f('ck_matriculas_bolsa'),
        'matriculas',
        "bolsa IN ('nenhuma', 'parcial', 'integral')",
    )
