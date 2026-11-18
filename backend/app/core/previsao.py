"""Previsão de receita (RF21, RF22, RN11): quanto deve entrar de mensalidades em cada mês.

A previsão vem das matrículas, não dos lançamentos: é a soma das mensalidades das matrículas em
vigor no mês. Patrocínios, editais e doações não entram, porque não são fixos (RN11).

"Em vigor" segue a mesma regra da geração das mensalidades: a matrícula começou até o último
dia do mês e não foi encerrada antes do primeiro. Se o aluno tem duas no mesmo mês (saiu e
voltou), vale a mais recente. Bolsa integral não paga, e a mensalidade do aluno apadrinhado é
cobrada da empresa, não do responsável: as duas ficam de fora desta conta.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import tempo
from app.models import Mensalidade, Pagamento
from app.models.matricula import Bolsa, Matricula
from app.models.mensalidade import StatusMensalidade

# Mês atual e os 11 seguintes (RF22)
MESES = 12
NAO_PAGAM_A_MENSALIDADE = (Bolsa.INTEGRAL, Bolsa.APADRINHADA)


@dataclass(frozen=True)
class MatriculaPrevista:
    """Só o que a conta precisa de uma matrícula."""

    id: int
    aluno_id: int
    data_inicio: date
    data_encerramento: date | None
    valor_mensalidade: Decimal
    bolsa: Bolsa


@dataclass(frozen=True)
class MesPrevisto:
    mes: date
    previsto: Decimal
    # Quantos alunos pagam mensalidade no mês
    alunos: int


@dataclass(frozen=True)
class MesAtual:
    previsao: MesPrevisto
    # Pagamentos (não cancelados) das mensalidades deste mês
    recebido: Decimal
    # Mensalidades deste mês isentas ou canceladas: estavam previstas, mas não vão entrar
    dispensado: Decimal
    falta: Decimal


@dataclass(frozen=True)
class Previsao:
    atual: MesAtual
    meses: list[MesPrevisto]
    total: Decimal


def ultimo_dia(mes: date) -> date:
    return tempo.mes_seguinte(mes) - timedelta(days=1)


def previsto_no_mes(matriculas: Iterable[MatriculaPrevista], mes: date) -> MesPrevisto:
    """Soma as mensalidades das matrículas em vigor no mês (`mes` é o dia 1). Função pura."""
    ultimo = ultimo_dia(mes)
    vale_no_mes: dict[int, MatriculaPrevista] = {}
    # A mais recente de cada aluno primeiro, como na geração das mensalidades
    for matricula in sorted(matriculas, key=lambda m: (m.data_inicio, m.id), reverse=True):
        em_vigor = matricula.data_inicio <= ultimo and (
            matricula.data_encerramento is None or matricula.data_encerramento >= mes
        )
        if em_vigor:
            vale_no_mes.setdefault(matricula.aluno_id, matricula)
    pagam = [m for m in vale_no_mes.values() if m.bolsa not in NAO_PAGAM_A_MENSALIDADE]
    return MesPrevisto(
        mes=mes,
        previsto=sum((m.valor_mensalidade for m in pagam), Decimal("0.00")),
        alunos=len(pagam),
    )


def _matriculas(db: Session, de: date, ate: date) -> list[MatriculaPrevista]:
    """As matrículas que podem estar em vigor em algum dia de `de` a `ate`. Uma consulta só."""
    linhas = db.execute(
        select(
            Matricula.id,
            Matricula.aluno_id,
            Matricula.data_inicio,
            Matricula.data_encerramento,
            Matricula.valor_mensalidade,
            Matricula.bolsa,
        ).where(
            Matricula.data_inicio <= ate,
            or_(Matricula.data_encerramento.is_(None), Matricula.data_encerramento >= de),
        )
    ).all()
    return [MatriculaPrevista(*linha) for linha in linhas]


def _do_mes(db: Session, mes: date, previsao: MesPrevisto) -> MesAtual:
    """O que da previsão do mês já entrou, e o que não vai entrar porque foi isentado."""
    das_familias = (Mensalidade.competencia == mes, Mensalidade.cobranca_id.is_(None))
    recebido = db.scalar(
        select(func.coalesce(func.sum(Pagamento.valor_pago), 0))
        .join(Mensalidade, Pagamento.mensalidade_id == Mensalidade.id)
        .where(*das_familias, Pagamento.cancelado_em.is_(None))
    )
    dispensado = db.scalar(
        select(func.coalesce(func.sum(Mensalidade.valor), 0)).where(
            *das_familias,
            Mensalidade.status.in_((StatusMensalidade.ISENTA, StatusMensalidade.CANCELADA)),
        )
    )
    recebido = Decimal(recebido).quantize(Decimal("0.01"))
    dispensado = Decimal(dispensado).quantize(Decimal("0.01"))
    # Pagou a mais (ou o valor da matrícula mudou depois): não falta nada, e nunca negativo
    falta = max(previsao.previsto - recebido - dispensado, Decimal("0.00"))
    return MesAtual(previsao=previsao, recebido=recebido, dispensado=dispensado, falta=falta)


def previsao_de_receita(db: Session) -> Previsao:
    """A previsão do mês atual e dos 11 seguintes (RF21, RF22)."""
    primeiro = tempo.hoje().replace(day=1)
    meses = [primeiro]
    for _ in range(MESES - 1):
        meses.append(tempo.mes_seguinte(meses[-1]))
    matriculas = _matriculas(db, meses[0], ultimo_dia(meses[-1]))
    previstos = [previsto_no_mes(matriculas, mes) for mes in meses]
    return Previsao(
        atual=_do_mes(db, primeiro, previstos[0]),
        meses=previstos,
        total=sum((m.previsto for m in previstos), Decimal("0.00")),
    )
