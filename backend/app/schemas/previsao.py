from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.core.previsao import MesPrevisto, Previsao


class MesPrevistoLeitura(BaseModel):
    """A previsão de um mês: a soma das mensalidades das matrículas em vigor nele (RN11)."""

    mes: date
    previsto: Decimal
    # Quantos alunos pagam mensalidade no mês
    alunos: int


class MesAtualLeitura(MesPrevistoLeitura):
    """O mês atual, com o que da previsão já entrou e o que falta (RF21)."""

    recebido: Decimal
    # Mensalidades isentas ou canceladas: estavam previstas, mas não vão entrar
    dispensado: Decimal
    falta: Decimal


class PrevisaoLeitura(BaseModel):
    """A previsão do mês atual e dos 11 seguintes, mês a mês, com o total (RF21, RF22).

    Só mensalidades: patrocínios, editais e doações não são fixos e ficam de fora (RN11).
    """

    atual: MesAtualLeitura
    meses: list[MesPrevistoLeitura]
    total: Decimal


def _mes(mes: MesPrevisto) -> MesPrevistoLeitura:
    return MesPrevistoLeitura(mes=mes.mes, previsto=mes.previsto, alunos=mes.alunos)


def para_leitura(previsao: Previsao) -> PrevisaoLeitura:
    atual = previsao.atual
    return PrevisaoLeitura(
        atual=MesAtualLeitura(
            **_mes(atual.previsao).model_dump(),
            recebido=atual.recebido,
            dispensado=atual.dispensado,
            falta=atual.falta,
        ),
        meses=[_mes(mes) for mes in previsao.meses],
        total=previsao.total,
    )
