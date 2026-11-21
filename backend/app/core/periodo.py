"""Período do caixa (RF24): de um mês inicial até um mês final, de no máximo 12 meses.

O período é sempre de meses inteiros, do dia 1 do primeiro ao último dia do último. Vale a
mesma regra do caixa de um mês: conta o dia em que o dinheiro entrou ou saiu (RN10) e deixa de
fora os lançamentos cancelados (RN12).
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core import tempo
from app.core.fluxo import FluxoDoPeriodo, fluxo_entre
from app.core.saldo import SaldoDoMes, saldo_por_mes, somar_movimentos
from app.schemas.mensalidade import PRIMEIRO_MES_ACEITO

MAXIMO_DE_MESES = 12

ANTIGO_DEMAIS = "Esse mês é antigo demais"
NO_FUTURO = "Escolha o mês atual ou um mês anterior"
FIM_ANTES_DO_INICIO = "O mês final não pode ser antes do mês inicial"
MUITOS_MESES = f"O período pode ter no máximo {MAXIMO_DE_MESES} meses"


@dataclass(frozen=True)
class CaixaDoPeriodo:
    de: date
    ate: date
    # O movimento do período inteiro, com o fluxo por categoria
    total: FluxoDoPeriodo
    # Cada mês do período, do mais antigo ao mais novo, mesmo os sem movimento
    meses: list[SaldoDoMes]


def quantidade_de_meses(de: date, ate: date) -> int:
    """Quantos meses há de `de` até `ate`, os dois incluídos: de janeiro a março são 3."""
    return (ate.year - de.year) * 12 + ate.month - de.month + 1


def erro_do_periodo(de: date, ate: date, atual: date) -> tuple[str, str] | None:
    """Confere o período. Devolve o campo com o problema ("de" ou "ate") e a mensagem, ou nada.

    `de`, `ate` e `atual` são dias 1. O mês atual é o último que existe: nenhum lançamento tem
    data no futuro (RN09).
    """
    if de < PRIMEIRO_MES_ACEITO:
        return "de", ANTIGO_DEMAIS
    if ate < PRIMEIRO_MES_ACEITO:
        return "ate", ANTIGO_DEMAIS
    if de > atual:
        return "de", NO_FUTURO
    if ate > atual:
        return "ate", NO_FUTURO
    if ate < de:
        return "ate", FIM_ANTES_DO_INICIO
    if quantidade_de_meses(de, ate) > MAXIMO_DE_MESES:
        return "ate", MUITOS_MESES
    return None


def caixa_do_periodo(db: Session, de: date, ate: date) -> CaixaDoPeriodo:
    """O caixa dos meses de `de` até `ate` (dois dias 1, incluídos): o total e cada mês.

    O total é a soma dos meses, e não outra conta: assim o total e a lista fecham sempre, mesmo
    que alguém registre um lançamento no meio do cálculo.
    """
    meses = saldo_por_mes(db, de, ate)
    total = fluxo_entre(db, de, tempo.mes_seguinte(ate), somar_movimentos(meses))
    return CaixaDoPeriodo(de=de, ate=ate, total=total, meses=meses)
