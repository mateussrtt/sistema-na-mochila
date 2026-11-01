"""cria a cobranca das empresas padrinhas

Revision ID: 4dae67b6e63e
Revises: 5121e027bf71
Create Date: 2026-11-01 18:22:38.602195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dae67b6e63e'
down_revision: Union[str, Sequence[str], None] = '5121e027bf71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('cobrancas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('padrinho_id', sa.Integer(), nullable=False),
    sa.Column('competencia', sa.Date(), nullable=False),
    sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.Enum('a_emitir', 'emitida', 'paga', 'cancelada', name='status', native_enum=False, create_constraint=True, length=10), server_default='a_emitir', nullable=False),
    sa.Column('data_vencimento', sa.Date(), nullable=False),
    sa.Column('limite_emissao', sa.Date(), nullable=True),
    sa.Column('numero_nota', sa.String(length=30), nullable=True),
    sa.Column('data_emissao', sa.Date(), nullable=True),
    sa.Column('emitida_por_id', sa.Integer(), nullable=True),
    sa.Column('emitida_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('criado_por_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('motivo_cancelamento', sa.String(length=255), nullable=True),
    sa.Column('cancelado_por_id', sa.Integer(), nullable=True),
    sa.Column('cancelado_em', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('valor > 0', name=op.f('ck_cobrancas_valor_positivo')),
    sa.CheckConstraint('EXTRACT(day FROM competencia) = 1', name=op.f('ck_cobrancas_competencia_dia_um')),
    sa.CheckConstraint('data_vencimento >= competencia', name=op.f('ck_cobrancas_vencimento_depois_da_competencia')),
    sa.CheckConstraint('limite_emissao IS NULL OR limite_emissao >= competencia', name=op.f('ck_cobrancas_limite_depois_da_competencia')),
    sa.CheckConstraint('data_emissao IS NULL OR data_vencimento >= data_emissao', name=op.f('ck_cobrancas_vencimento_depois_da_emissao')),
    sa.CheckConstraint("status <> 'a_emitir' OR (numero_nota IS NULL AND data_emissao IS NULL)", name=op.f('ck_cobrancas_a_emitir_sem_nota')),
    sa.CheckConstraint("status NOT IN ('emitida', 'paga') OR (numero_nota IS NOT NULL AND data_emissao IS NOT NULL AND emitida_por_id IS NOT NULL AND emitida_em IS NOT NULL)", name=op.f('ck_cobrancas_emitida_com_nota')),
    sa.CheckConstraint("status <> 'cancelada' OR (motivo_cancelamento IS NOT NULL AND cancelado_por_id IS NOT NULL AND cancelado_em IS NOT NULL)", name=op.f('ck_cobrancas_cancelada_com_motivo')),
    sa.ForeignKeyConstraint(['cancelado_por_id'], ['usuarios.id'], name=op.f('fk_cobrancas_cancelado_por_id_usuarios')),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], name=op.f('fk_cobrancas_criado_por_id_usuarios')),
    sa.ForeignKeyConstraint(['emitida_por_id'], ['usuarios.id'], name=op.f('fk_cobrancas_emitida_por_id_usuarios')),
    sa.ForeignKeyConstraint(['padrinho_id'], ['padrinhos.id'], name=op.f('fk_cobrancas_padrinho_id_padrinhos')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cobrancas'))
    )
    op.create_index(op.f('ix_cobrancas_competencia'), 'cobrancas', ['competencia'], unique=False)
    op.create_index(op.f('ix_cobrancas_padrinho_id'), 'cobrancas', ['padrinho_id'], unique=False)
    op.create_index('uq_cobrancas_padrinho_competencia_a_emitir', 'cobrancas', ['padrinho_id', 'competencia'], unique=True, postgresql_where=sa.text("status = 'a_emitir'"))
    op.create_index('uq_cobrancas_numero_nota', 'cobrancas', [sa.literal_column('lower(numero_nota)')], unique=True)

    op.create_table('pagamentos_cobranca',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cobranca_id', sa.Integer(), nullable=False),
    sa.Column('data_pagamento', sa.Date(), nullable=False),
    sa.Column('valor_pago', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('forma_pagamento', sa.Enum('pix', 'transferencia', 'boleto', 'outra', name='forma_pagamento_cobranca', native_enum=False, create_constraint=True, length=15), nullable=False),
    sa.Column('observacao', sa.String(length=255), nullable=True),
    sa.Column('criado_por_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('cancelado_em', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('valor_pago > 0', name=op.f('ck_pagamentos_cobranca_valor_positivo')),
    sa.ForeignKeyConstraint(['cobranca_id'], ['cobrancas.id'], name=op.f('fk_pagamentos_cobranca_cobranca_id_cobrancas')),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], name=op.f('fk_pagamentos_cobranca_criado_por_id_usuarios')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pagamentos_cobranca'))
    )
    op.create_index(op.f('ix_pagamentos_cobranca_cobranca_id'), 'pagamentos_cobranca', ['cobranca_id'], unique=False)
    op.create_index('uq_pagamentos_cobranca_ativo', 'pagamentos_cobranca', ['cobranca_id'], unique=True, postgresql_where=sa.text('cancelado_em IS NULL'))

    op.add_column('mensalidades', sa.Column('cobranca_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_mensalidades_cobranca_id'), 'mensalidades', ['cobranca_id'], unique=False)
    op.create_foreign_key(op.f('fk_mensalidades_cobranca_id_cobrancas'), 'mensalidades', 'cobrancas', ['cobranca_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # As mensalidades dos apadrinhados só existem por causa das cobranças: sem elas, ficariam soltas
    # e passariam a ser cobradas dos responsáveis
    op.execute("DELETE FROM mensalidades WHERE cobranca_id IS NOT NULL")
    op.drop_constraint(op.f('fk_mensalidades_cobranca_id_cobrancas'), 'mensalidades', type_='foreignkey')
    op.drop_index(op.f('ix_mensalidades_cobranca_id'), table_name='mensalidades')
    op.drop_column('mensalidades', 'cobranca_id')
    op.drop_table('pagamentos_cobranca')
    op.drop_table('cobrancas')
