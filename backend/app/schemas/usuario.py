from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Perfil
from app.schemas.comum import texto_valido


class LoginEntrada(BaseModel):
    """E-mail e senha digitados na tela de login.

    O e-mail não passa por validação de formato: um e-mail mal digitado só não encontra
    ninguém, e a resposta é a mesma de uma senha errada.
    """

    email: str = Field(min_length=1, max_length=254)
    senha: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def email_minusculo(cls, valor: object) -> object:
        return valor.strip().lower() if isinstance(valor, str) else valor

    @field_validator("email")
    @classmethod
    def sem_caractere_invalido(cls, valor: str) -> str:
        return texto_valido(valor) or ""


class UsuarioLeitura(BaseModel):
    """Usuário como a API devolve. A senha nunca sai daqui."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    perfil: Perfil
    ativo: bool


class LoginResposta(BaseModel):
    token: str
    usuario: UsuarioLeitura
