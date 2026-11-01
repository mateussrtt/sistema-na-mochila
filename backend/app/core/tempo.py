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
