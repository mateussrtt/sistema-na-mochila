import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, field_validator

from app.core import tempo
from app.models import Bolsa, FormaDePagamento, SituacaoMensalidade, StatusMensalidade
from app.schemas.comum import texto_valido
from app.schemas.matricula import AlunoResumo, exige_data

# Só aceita dígitos de 0 a 9 (o "\d" do Python aceitaria também dígitos de outros alfabetos)
_MES = re.compile(r"^([0-9]{4})-([0-9]{2})(?:-([0-9]{2}))?$")

PRIMEIRO_MES_ACEITO = date(2000, 1, 1)
MENSAGEM_DO_MES = "Informe o mês no formato AAAA-MM"
OBSERVACAO_MAXIMA = 255
MOTIVO_MINIMO = 3
MOTIVO_MAXIMO = 255


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


class PagamentoEntrada(BaseModel):
    """Dados enviados para registrar o pagamento de uma mensalidade (RF10)."""

    data_pagamento: date
    valor_pago: Decimal
    forma_pagamento: FormaDePagamento
    observacao: str | None = None

    @field_validator("data_pagamento", mode="before")
    @classmethod
    def exige_data_do_pagamento(cls, valor: object) -> object:
        return exige_data(valor, "Informe a data do pagamento")

    @field_validator("data_pagamento")
    @classmethod
    def data_possivel(cls, valor: date) -> date:
        # RN09: o dinheiro já entrou, então a data não pode ser futura
        if valor > tempo.hoje():
            raise ValueError("A data do pagamento não pode ser no futuro")
        if valor < PRIMEIRO_MES_ACEITO:
            raise ValueError("Essa data é antiga demais")
        return valor

    @field_validator("valor_pago", mode="before")
    @classmethod
    def le_valor(cls, valor: object) -> object:
        if isinstance(valor, str):
            valor = valor.strip().replace(",", ".")
        if valor is None or valor == "":
            raise ValueError("Informe o valor pago")
        try:
            numero = Decimal(str(valor))
        except InvalidOperation:
            raise ValueError("Informe um valor válido") from None
        if not numero.is_finite():
            # NaN e Infinity passariam como Decimal, mas quebram a resposta de erro em JSON
            raise ValueError("Informe um valor válido")
        return numero

    @field_validator("valor_pago")
    @classmethod
    def valor_possivel(cls, valor: Decimal) -> Decimal:
        if valor <= 0:
            raise ValueError("O valor pago deve ser maior que zero")
        if valor.as_tuple().exponent < -2:
            raise ValueError("Use no máximo 2 casas decimais")
        if valor >= Decimal(10) ** 8:
            raise ValueError("O valor pago é alto demais")
        return valor.quantize(Decimal("0.01"))

    @field_validator("forma_pagamento", mode="before")
    @classmethod
    def forma_conhecida(cls, valor: object) -> object:
        if isinstance(valor, str) and valor in {forma.value for forma in FormaDePagamento}:
            return valor
        raise ValueError("Escolha a forma de pagamento: PIX, dinheiro, boleto ou outra")

    @field_validator("observacao")
    @classmethod
    def observacao_limpa(cls, valor: str | None) -> str | None:
        texto = texto_valido(valor)
        texto = texto.strip() if texto else None
        if texto and len(texto) > OBSERVACAO_MAXIMA:
            raise ValueError(f"Use no máximo {OBSERVACAO_MAXIMA} caracteres na observação")
        return texto or None


class MotivoEntrada(BaseModel):
    """Motivo informado pelo administrador ao isentar ou cancelar uma mensalidade (RF14)."""

    motivo: str

    @field_validator("motivo", mode="before")
    @classmethod
    def exige_motivo(cls, valor: object) -> object:
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            raise ValueError("Informe o motivo")
        return valor

    @field_validator("motivo")
    @classmethod
    def motivo_limpo(cls, valor: str) -> str:
        texto = texto_valido(valor).strip()
        if len(texto) < MOTIVO_MINIMO:
            raise ValueError(f"Explique o motivo com pelo menos {MOTIVO_MINIMO} letras")
        if len(texto) > MOTIVO_MAXIMO:
            raise ValueError(f"Use no máximo {MOTIVO_MAXIMO} caracteres no motivo")
        return " ".join(texto.split())


class PagamentoLeitura(BaseModel):
    """O pagamento ativo de uma mensalidade, com quem registrou (RF26)."""

    data_pagamento: date
    valor_pago: Decimal
    forma_pagamento: FormaDePagamento
    observacao: str | None
    registrado_por: str
    registrado_em: datetime


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
    # Só a mensalidade paga tem pagamento
    pagamento: PagamentoLeitura | None = None
    # Só a mensalidade isenta ou cancelada tem motivo, quem alterou e quando (RF14, RF26)
    motivo: str | None = None
    alterado_por: str | None = None
    alterado_em: datetime | None = None
