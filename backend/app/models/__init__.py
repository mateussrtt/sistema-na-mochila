"""Modelos do banco de dados.

Cada tabela fica em um arquivo próprio e deve ser importada aqui,
para o Alembic enxergá-la ao gerar as migrações.
"""

from app.db.base import Base
from app.models.aluno import Aluno, aluno_responsavel
from app.models.cobranca import (
    Cobranca,
    FormaDePagamentoCobranca,
    PagamentoCobranca,
    SituacaoCobranca,
    StatusCobranca,
    emissao_atrasada,
    situacao_da_cobranca,
)
from app.models.matricula import Bolsa, Matricula, SituacaoMatricula
from app.models.mensalidade import (
    DIA_DO_VENCIMENTO,
    Mensalidade,
    SituacaoMensalidade,
    StatusMensalidade,
    data_de_vencimento,
    esta_atrasada,
    situacao_da_mensalidade,
)
from app.models.padrinho import Padrinho
from app.models.pagamento import FormaDePagamento, Pagamento
from app.models.responsavel import Responsavel
from app.models.usuario import Perfil, Usuario

__all__ = [
    "DIA_DO_VENCIMENTO",
    "Aluno",
    "Base",
    "Bolsa",
    "Cobranca",
    "FormaDePagamento",
    "FormaDePagamentoCobranca",
    "Matricula",
    "Mensalidade",
    "Padrinho",
    "Pagamento",
    "PagamentoCobranca",
    "Perfil",
    "Responsavel",
    "SituacaoCobranca",
    "SituacaoMatricula",
    "SituacaoMensalidade",
    "StatusCobranca",
    "StatusMensalidade",
    "Usuario",
    "aluno_responsavel",
    "data_de_vencimento",
    "emissao_atrasada",
    "esta_atrasada",
    "situacao_da_cobranca",
    "situacao_da_mensalidade",
]
