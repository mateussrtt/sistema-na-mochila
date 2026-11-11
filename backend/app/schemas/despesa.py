from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core import tempo
from app.schemas.cancelamento import CancelamentoLeitura
from app.schemas.comum import ID_MAXIMO, conferir_dinheiro, ler_dinheiro, texto_valido
from app.schemas.matricula import exige_data
from app.schemas.mensalidade import PRIMEIRO_MES_ACEITO, exige_motivo, motivo_limpo

NOME_MINIMO = 2
NOME_MAXIMO = 60
DESCRICAO_MINIMA = 3
DESCRICAO_MAXIMA = 255
FAVORECIDO_MINIMO = 2
FAVORECIDO_MAXIMO = 120


def texto_obrigatorio(valor: object, mensagem: str) -> object:
    """Texto em branco (ou ausente) vira a mensagem em português, em vez de "Field required"."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValueError(mensagem)
    return valor


def texto_com_tamanho(valor: str, minimo: int, maximo: int, nome: str) -> str:
    """Tira espaços repetidos e confere o tamanho. Recusa o caractere nulo."""
    texto = " ".join((texto_valido(valor) or "").split())
    if len(texto) < minimo:
        raise ValueError(f"{nome} deve ter pelo menos {minimo} letras")
    if len(texto) > maximo:
        raise ValueError(f"{nome} deve ter no máximo {maximo} caracteres")
    return texto


class CategoriaDespesaEntrada(BaseModel):
    """Dados enviados para cadastrar ou editar uma categoria de despesa (RF15)."""

    nome: str
    ativo: bool = True

    @model_validator(mode="before")
    @classmethod
    def nome_ausente_vira_vazio(cls, dados: object) -> object:
        # O campo continua obrigatório (e assim sai no OpenAPI). Isto só faz o campo que nem veio
        # no corpo cair na mesma mensagem em português do campo em branco
        if isinstance(dados, dict):
            return {"nome": None} | dados
        return dados

    @field_validator("nome", mode="before")
    @classmethod
    def exige_nome(cls, valor: object) -> object:
        return texto_obrigatorio(valor, "Informe o nome da categoria")

    @field_validator("nome")
    @classmethod
    def nome_limpo(cls, valor: str) -> str:
        return texto_com_tamanho(valor, NOME_MINIMO, NOME_MAXIMO, "O nome da categoria")

    @field_validator("ativo", mode="before")
    @classmethod
    def ativo_e_verdadeiro_ou_falso(cls, valor: object) -> object:
        # O padrão do pydantic aceita 0, 1 e textos como "no" como verdadeiro/falso: aqui só vale
        # true ou false, para um valor torto não desativar a categoria sem querer
        if not isinstance(valor, bool):
            raise ValueError("Informe verdadeiro ou falso")
        return valor


class CategoriaDespesaLeitura(BaseModel):
    """Categoria como a API devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    ativo: bool


class DespesaEntrada(BaseModel):
    """Dados enviados para registrar uma despesa (RF16)."""

    data_despesa: date
    valor: Decimal
    categoria_id: int
    descricao: str
    favorecido: str

    @model_validator(mode="before")
    @classmethod
    def ausentes_viram_vazios(cls, dados: object) -> object:
        # Os campos continuam obrigatórios (e assim saem no OpenAPI). Isto só faz o campo que nem
        # veio no corpo cair na mesma mensagem em português do campo em branco
        if isinstance(dados, dict):
            campos = ("data_despesa", "valor", "categoria_id", "descricao", "favorecido")
            return dict.fromkeys(campos) | dados
        return dados

    @field_validator("data_despesa", mode="before")
    @classmethod
    def exige_data_da_despesa(cls, valor: object) -> object:
        return exige_data(valor, "Informe a data da despesa")

    @field_validator("data_despesa")
    @classmethod
    def data_possivel(cls, valor: date) -> date:
        # RN09: o dinheiro já saiu, então a data não pode ser futura
        if valor > tempo.hoje():
            raise ValueError("A data da despesa não pode ser no futuro")
        if valor < PRIMEIRO_MES_ACEITO:
            raise ValueError("Essa data é antiga demais")
        return valor

    @field_validator("valor", mode="before")
    @classmethod
    def le_valor(cls, valor: object) -> object:
        return ler_dinheiro(valor, "Informe o valor da despesa")

    @field_validator("valor")
    @classmethod
    def valor_possivel(cls, valor: Decimal) -> Decimal:
        return conferir_dinheiro(valor, "O valor da despesa")

    @field_validator("categoria_id", mode="before")
    @classmethod
    def exige_categoria(cls, valor: object) -> object:
        # RN08: toda despesa tem categoria. Em Python, True vale 1: não pode valer como id
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            raise ValueError("Escolha a categoria da despesa")
        if isinstance(valor, bool):
            raise ValueError("Escolha a categoria da despesa")
        return valor

    @field_validator("categoria_id")
    @classmethod
    def categoria_possivel(cls, valor: int) -> int:
        if not 0 < valor <= ID_MAXIMO:
            raise ValueError("Escolha a categoria da despesa")
        return valor

    @field_validator("descricao", mode="before")
    @classmethod
    def exige_descricao(cls, valor: object) -> object:
        return texto_obrigatorio(valor, "Informe a descrição da despesa")

    @field_validator("descricao")
    @classmethod
    def descricao_limpa(cls, valor: str) -> str:
        return texto_com_tamanho(valor, DESCRICAO_MINIMA, DESCRICAO_MAXIMA, "A descrição")

    @field_validator("favorecido", mode="before")
    @classmethod
    def exige_favorecido(cls, valor: object) -> object:
        return texto_obrigatorio(valor, "Informe para quem foi pago")

    @field_validator("favorecido")
    @classmethod
    def favorecido_limpo(cls, valor: str) -> str:
        return texto_com_tamanho(valor, FAVORECIDO_MINIMO, FAVORECIDO_MAXIMO, "O favorecido")


class DespesaLeitura(BaseModel):
    """Despesa como a API devolve, com a categoria e quem registrou (RF26)."""

    id: int
    data_despesa: date
    valor: Decimal
    categoria: CategoriaDespesaLeitura
    descricao: str
    favorecido: str
    registrado_por: str
    registrado_em: datetime
    # Lançamento cancelado continua na lista, com o motivo, mas não entra nos totais (RF17)
    cancelamento: CancelamentoLeitura | None = None
    # Correção: o lançamento novo aponta para o cancelado que ele substitui, e vice-versa
    substitui_id: int | None = None
    substituida_por_id: int | None = None


class DespesaCorrecao(DespesaEntrada):
    """Os dados certos da despesa e o motivo da correção (RF17).

    A despesa errada é cancelada com esse motivo e uma nova é registrada no lugar, apontando para
    ela.
    """

    motivo: str

    @model_validator(mode="before")
    @classmethod
    def motivo_ausente_vira_vazio(cls, dados: object) -> object:
        if isinstance(dados, dict):
            return {"motivo": None} | dados
        return dados

    @field_validator("motivo", mode="before")
    @classmethod
    def exige_o_motivo(cls, valor: object) -> object:
        return exige_motivo(valor)

    @field_validator("motivo")
    @classmethod
    def limpa_o_motivo(cls, valor: str) -> str:
        return motivo_limpo(valor)
