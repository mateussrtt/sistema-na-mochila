"""Modelos do banco de dados.

Cada tabela fica em um arquivo próprio e deve ser importada aqui,
para o Alembic enxergá-la ao gerar as migrações.
"""

from app.db.base import Base
from app.models.aluno import Aluno, aluno_responsavel
from app.models.responsavel import Responsavel

__all__ = ["Aluno", "Base", "Responsavel", "aluno_responsavel"]
