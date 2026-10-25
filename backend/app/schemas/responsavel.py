import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.comum import texto_valido

class ResponsavelEntrada(BaseModel):
    """Dados enviados para cadastrar ou editar um responsável."""

    nome: str = Field(min_length=2, max_length=120)
    telefone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None

    @field_validator("nome", mode="before")
    @classmethod
    def limpa_nome(cls, valor: str) -> str:
        return " ".join(valor.split()) if isinstance(valor, str) else valor

    @field_validator("telefone", "email", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, valor: str | None) -> str | None:
        if isinstance(valor, str):
            valor = valor.strip()
        return valor or None

    @field_validator("nome", "telefone")
    @classmethod
    def sem_caractere_invalido(cls, valor: str | None) -> str | None:
        return texto_valido(valor)

    @field_validator("telefone")
    @classmethod
    def valida_telefone(cls, valor: str | None) -> str | None:
        if valor is not None and len(re.sub(r"\D", "", valor)) not in (10, 11):
            raise ValueError("Telefone deve ter DDD e 8 ou 9 dígitos")
        return valor

    @model_validator(mode="after")
    def exige_contato(self) -> "ResponsavelEntrada":
        if not self.telefone and not self.email:
            raise ValueError("Informe ao menos um telefone ou e-mail")
        return self


class ResponsavelLeitura(BaseModel):
    """Responsável como a API devolve."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    telefone: str | None
    email: str | None
