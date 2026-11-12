"""A data de hoje no horário de Brasília.

O servidor roda em UTC. Sem este ajuste, depois das 21h em Brasília o servidor já estaria
no dia seguinte e uma mensalidade que vence no dia 10 apareceria como atrasada três horas
antes da hora (RN07).
"""

from datetime import date, datetime, timedelta, timezone

# O Brasil não usa horário de verão desde 2019, então o deslocamento é fixo
BRASILIA = timezone(timedelta(hours=-3))


def hoje() -> date:
    return datetime.now(BRASILIA).date()


def mes_seguinte(primeiro_dia: date) -> date:
    """O dia 1 do mês seguinte, para usar como limite de um mês: `>= mês` e `< mês seguinte`.

    Em dezembro de 9999 não existe "mês seguinte" no calendário: devolve o último dia possível,
    em vez de estourar um erro.
    """
    if primeiro_dia.month == 12:
        return date(primeiro_dia.year + 1, 1, 1) if primeiro_dia.year < date.max.year else date.max
    return primeiro_dia.replace(month=primeiro_dia.month + 1, day=1)
