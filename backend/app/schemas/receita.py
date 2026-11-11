from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core import tempo
from app.schemas.comum import ID_MAXIMO, conferir_dinheiro, ler_dinheiro
from app.schemas.despesa import texto_com_tamanho, texto_obrigatorio
from app.schemas.matricula import exige_data
from app.schemas.mensalidade import PRIMEIRO_MES_ACEITO

NOME_MINIMO = 2
NOME_MAXIMO = 60
DESCRICAO_MINIMA = 3
DESCRICAO_MAXIMA = 255
ORIGEM_MINIMO = 2
ORIGEM_MAXIMO = 120


class CategoriaReceitaEntrada(BaseModel):
    """Dados enviados para cadastrar ou editar uma categoria de receita (RF18)."""

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


class CategoriaReceitaLeitura(BaseModel):
    """Categoria como a API devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    ativo: bool


class ReceitaEntrada(BaseModel):
    """Dados enviados para registrar uma receita (RF18)."""

    data_receita: date
    valor: Decimal
    categoria_id: int
    origem: str
    descricao: str | None = None

    @model_validator(mode="before")
    @classmethod
    def ausentes_viram_vazios(cls, dados: object) -> object:
        # Os campos continuam obrigatórios (e assim saem no OpenAPI). Isto só faz o campo que nem
        # veio no corpo cair na mesma mensagem em português do campo em branco
        if isinstance(dados, dict):
            campos = ("data_receita", "valor", "categoria_id", "origem")
            return dict.fromkeys(campos) | dados
        return dados

    @field_validator("data_receita", mode="before")
    @classmethod
    def exige_data_da_receita(cls, valor: object) -> object:
        return exige_data(valor, "Informe a data da receita")

    @field_validator("data_receita")
    @classmethod
    def data_possivel(cls, valor: date) -> date:
        # RN09: o dinheiro já entrou, então a data não pode ser futura
        if valor > tempo.hoje():
            raise ValueError("A data da receita não pode ser no futuro")
        if valor < PRIMEIRO_MES_ACEITO:
            raise ValueError("Essa data é antiga demais")
        return valor

    @field_validator("valor", mode="before")
    @classmethod
    def le_valor(cls, valor: object) -> object:
        return ler_dinheiro(valor, "Informe o valor da receita")

    @field_validator("valor")
    @classmethod
    def valor_possivel(cls, valor: Decimal) -> Decimal:
        return conferir_dinheiro(valor, "O valor da receita")

    @field_validator("categoria_id", mode="before")
    @classmethod
    def exige_categoria(cls, valor: object) -> object:
        # RN08: toda receita tem categoria. Em Python, True vale 1: não pode valer como id
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            raise ValueError("Escolha a categoria da receita")
        if isinstance(valor, bool):
            raise ValueError("Escolha a categoria da receita")
        return valor

    @field_validator("categoria_id")
    @classmethod
    def categoria_possivel(cls, valor: int) -> int:
        if not 0 < valor <= ID_MAXIMO:
            raise ValueError("Escolha a categoria da receita")
        return valor

    @field_validator("origem", mode="before")
    @classmethod
    def exige_origem(cls, valor: object) -> object:
        # RN08: toda entrada tem origem
        return texto_obrigatorio(valor, "Informe quem pagou")

    @field_validator("origem")
    @classmethod
    def origem_limpa(cls, valor: str) -> str:
        return texto_com_tamanho(valor, ORIGEM_MINIMO, ORIGEM_MAXIMO, "A origem")

    @field_validator("descricao")
    @classmethod
    def descricao_limpa(cls, valor: str | None) -> str | None:
        # Opcional: em branco vira vazio (None) no banco
        if valor is None or not valor.strip():
            return None
        return texto_com_tamanho(valor, DESCRICAO_MINIMA, DESCRICAO_MAXIMA, "A descrição")


class ReceitaLeitura(BaseModel):
    """Receita como a API devolve, com a categoria e quem registrou (RF26)."""

    id: int
    data_receita: date
    valor: Decimal
    categoria: CategoriaReceitaLeitura
    origem: str
    descricao: str | None
    registrado_por: str
    registrado_em: datetime
