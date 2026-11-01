import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.core import tempo
from app.models import Bolsa, SituacaoMensalidade, StatusMensalidade
from app.schemas.matricula import AlunoResumo

# Só aceita dígitos de 0 a 9 (o "\d" do Python aceitaria também dígitos de outros alfabetos)
_MES = re.compile(r"^([0-9]{4})-([0-9]{2})(?:-([0-9]{2}))?$")

PRIMEIRO_MES_ACEITO = date(2000, 1, 1)
MENSAGEM_DO_MES = "Informe o mês no formato AAAA-MM"


def primeiro_dia_do_mes(valor: object) -> date:
    """Aceita "AAAA-MM", "AAAA-MM-DD" ou uma data e devolve o dia 1 desse mês."""
    if isinstance(valor, date):
        return valor.replace(day=1)
    if isinstance(valor, str):
        achado = _MES.match(valor.strip())
        if achado:
            ano, mes, dia = int(achado[1]), int(achado[2]), int(achado[3] or 1)
            try:
                return date(ano, mes, dia).replace(day=1)
            except ValueError:
                pass
    raise ValueError(MENSAGEM_DO_MES)


def ultimo_mes_para_gerar() -> date:
    """O mês seguinte ao atual: dá para preparar o próximo mês, mas não os de muito adiante."""
    hoje = tempo.hoje()
    if hoje.month == 12:
        return date(hoje.year + 1, 1, 1)
    return date(hoje.year, hoje.month + 1, 1)


class GeracaoEntrada(BaseModel):
    """Mês para o qual as mensalidades serão geradas."""

    competencia: date

    @field_validator("competencia", mode="before")
    @classmethod
    def le_mes(cls, valor: object) -> date:
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            raise ValueError("Informe o mês das mensalidades")
        return primeiro_dia_do_mes(valor)

    @field_validator("competencia")
    @classmethod
    def mes_possivel(cls, valor: date) -> date:
        if valor < PRIMEIRO_MES_ACEITO:
            raise ValueError("Esse mês é antigo demais")
        if valor > ultimo_mes_para_gerar():
            raise ValueError("Só é possível gerar até o mês seguinte ao atual")
        return valor


class GeracaoResultado(BaseModel):
    """O que a geração fez, para a tela explicar o resultado."""

    competencia: date
    geradas: int
    ja_existiam: int
    bolsa_integral: int
    ainda_nao_comecaram: int


class MensalidadeLeitura(BaseModel):
    """Mensalidade como a API devolve, com o aluno e a situação já calculada."""

    id: int
    matricula_id: int
    aluno: AlunoResumo
    bolsa: Bolsa
    competencia: date
    valor: Decimal
    data_vencimento: date
    status: StatusMensalidade
    situacao: SituacaoMensalidade
    dias_em_atraso: int
