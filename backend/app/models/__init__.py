"""Modelos do banco de dados.

Cada tabela fica em um arquivo próprio (aluno.py, responsavel.py, matricula.py,
mensalidade.py, despesa.py, receita.py, usuario.py...) e deve ser importada
aqui, para o Alembic enxergá-la ao gerar as migrações.
"""

from app.db.base import Base

__all__ = ["Base"]
