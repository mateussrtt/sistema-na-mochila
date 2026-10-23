from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.responsavel import ResponsavelLeitura


class AlunoEntrada(BaseModel):
    """Dados enviados para cadastrar ou editar um aluno."""

    nome: str = Field(min_length=2, max_length=120)
    data_nascimento: date | None = None
    escola: str | None = Field(default=None, max_length=120)
    municipio: str | None = Field(default=None, max_length=80)
    responsavel_ids: list[int] = Field(min_length=1)
    ativo: bool = True

    @field_validator("nome", mode="before")
    @classmethod
    def limpa_nome(cls, valor: str) -> str:
        return " ".join(valor.split()) if isinstance(valor, str) else valor

    @field_validator("escola", "municipio", "data_nascimento", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, valor: object) -> object:
        if isinstance(valor, str):
            valor = valor.strip()
        return valor or None

    @field_validator("data_nascimento")
    @classmethod
    def nascimento_no_passado(cls, valor: date | None) -> date | None:
        if valor is not None and valor > date.today():
            raise ValueError("A data de nascimento não pode ser no futuro")
        return valor

    @field_validator("responsavel_ids")
    @classmethod
    def sem_repeticao(cls, valor: list[int]) -> list[int]:
        return list(dict.fromkeys(valor))


class AlunoLeitura(BaseModel):
    """Aluno como a API devolve, já com os responsáveis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    data_nascimento: date | None
    escola: str | None
    municipio: str | None
    ativo: bool
    responsaveis: list[ResponsavelLeitura]
