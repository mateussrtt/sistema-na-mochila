"""Modelos do banco de dados.

Cada tabela fica em um arquivo próprio e deve ser importada aqui,
para o Alembic enxergá-la ao gerar as migrações.
"""

from app.db.base import Base
from app.models.aluno import Aluno, aluno_responsavel
from app.models.matricula import Bolsa, Matricula, SituacaoMatricula
from app.models.responsavel import Responsavel
from app.models.usuario import Perfil, Usuario

__all__ = [
    "Aluno",
    "Base",
    "Bolsa",
    "Matricula",
    "Perfil",
    "Responsavel",
    "SituacaoMatricula",
    "Usuario",
    "aluno_responsavel",
]
