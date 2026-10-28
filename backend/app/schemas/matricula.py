from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models import Bolsa, SituacaoMatricula
from app.schemas.comum import ID_MAXIMO


def exige_data(valor: object, mensagem: str) -> object:
    """Troca data vazia por uma mensagem em português, em vez do erro padrão em inglês."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValueError(mensagem)
    return valor


class MatriculaEntrada(BaseModel):
    """Dados enviados para matricular um aluno."""

    aluno_id: int = Field(gt=0, le=ID_MAXIMO)
    data_inicio: date
    bolsa: Bolsa = Bolsa.NENHUMA
    # Com bolsa integral o valor pode ficar em branco: a mensalidade é zero
    valor_mensalidade: Decimal | None = Field(default=None, validate_default=True)

    @field_validator("data_inicio", mode="before")
    @classmethod
    def exige_inicio(cls, valor: object) -> object:
        return exige_data(valor, "Informe a data de início")

    @field_validator("valor_mensalidade", mode="before")
    @classmethod
    def le_valor(cls, valor: object) -> object:
        if isinstance(valor, str):
            valor = valor.strip().replace(",", ".")
        if valor is None or valor == "":
            return None
        try:
            numero = Decimal(str(valor))
        except InvalidOperation:
            raise ValueError("Informe um valor válido") from None
        if not numero.is_finite():
            # NaN e Infinity passariam como Decimal, mas quebram a resposta de erro em JSON
            raise ValueError("Informe um valor válido")
        return numero

    @field_validator("valor_mensalidade")
    @classmethod
    def valor_conforme_bolsa(cls, valor: Decimal | None, info: ValidationInfo) -> Decimal:
        if info.data.get("bolsa") == Bolsa.INTEGRAL:
            if valor not in (None, 0):
                raise ValueError("Com bolsa integral, a mensalidade é zero")
            return Decimal("0.00")
        if valor is None:
            raise ValueError("Informe o valor da mensalidade")
        if valor <= 0:
            raise ValueError("O valor da mensalidade deve ser maior que zero")
        if valor.as_tuple().exponent < -2:
            raise ValueError("Use no máximo 2 casas decimais")
        if valor >= Decimal(10) ** 8:
            raise ValueError("O valor da mensalidade é alto demais")
        return valor.quantize(Decimal("0.01"))


class MatriculaEncerramento(BaseModel):
    """Dados enviados para encerrar uma matrícula."""

    data_encerramento: date

    @field_validator("data_encerramento", mode="before")
    @classmethod
    def exige_encerramento(cls, valor: object) -> object:
        return exige_data(valor, "Informe a data de encerramento")

    @field_validator("data_encerramento")
    @classmethod
    def encerramento_no_passado(cls, valor: date) -> date:
        if valor > date.today():
            raise ValueError("A data de encerramento não pode ser no futuro")
        return valor


class AlunoResumo(BaseModel):
    """Dados do aluno que aparecem junto da matrícula."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    ativo: bool


class MatriculaLeitura(BaseModel):
    """Matrícula como a API devolve, já com o aluno."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    aluno: AlunoResumo
    data_inicio: date
    data_encerramento: date | None
    valor_mensalidade: Decimal
    bolsa: Bolsa
    situacao: SituacaoMatricula
