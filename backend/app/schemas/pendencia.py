from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class MensalidadeEmAtraso(BaseModel):
    """Uma mensalidade em aberto, com os dias de atraso já calculados."""

    id: int
    competencia: date
    valor: Decimal
    data_vencimento: date
    dias_em_atraso: int


class AlunoEmAtraso(BaseModel):
    """Aluno com as mensalidades em atraso. Só traz o necessário para cobrar (RN14)."""

    id: int
    nome: str
    ativo: bool
    total: Decimal
    mensalidades: list[MensalidadeEmAtraso]


class ContatoDoResponsavel(BaseModel):
    """Quem deve ser procurado e como."""

    id: int
    nome: str
    telefone: str | None
    email: str | None


class GrupoEmAtraso(BaseModel):
    """Os alunos que têm exatamente os mesmos responsáveis, numa pendência só.

    Cada aluno em atraso aparece em um único grupo, então a soma dos totais dos grupos é
    sempre igual ao total em aberto do resumo: nenhuma cobrança aparece repetida.
    """

    responsaveis: list[ContatoDoResponsavel]
    alunos: list[AlunoEmAtraso]
    total: Decimal
    maior_atraso: int


class ResumoDePendencias(BaseModel):
    """Totais do painel."""

    responsaveis: int
    alunos: int
    mensalidades: int
    total_em_aberto: Decimal


class Pendencias(BaseModel):
    """O painel de pendências (RF12): o resumo e a lista de pendências."""

    mes: date | None
    resumo: ResumoDePendencias
    grupos: list[GrupoEmAtraso]
