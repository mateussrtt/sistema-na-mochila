from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Perfil
from app.schemas.comum import texto_valido

SENHA_MINIMA = 8
SENHA_MAXIMA = 128


def senha_valida(valor: str) -> str:
    """Senha com tamanho mínimo. Espaços contam: a senha é guardada como foi digitada."""
    if len(valor) < SENHA_MINIMA:
        raise ValueError(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres")
    if len(valor) > SENHA_MAXIMA:
        raise ValueError(f"A senha pode ter no máximo {SENHA_MAXIMA} caracteres")
    return texto_valido(valor) or ""


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


class UsuarioDados(BaseModel):
    """Nome, e-mail e perfil, usados no cadastro e na edição de usuários."""

    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr = Field(max_length=254)
    perfil: Perfil

    @field_validator("nome", mode="before")
    @classmethod
    def limpa_nome(cls, valor: object) -> object:
        return " ".join(valor.split()) if isinstance(valor, str) else valor

    @field_validator("email", mode="before")
    @classmethod
    def email_minusculo(cls, valor: object) -> object:
        return valor.strip().lower() if isinstance(valor, str) else valor

    @field_validator("nome")
    @classmethod
    def sem_caractere_invalido(cls, valor: str) -> str:
        return texto_valido(valor) or ""


class UsuarioEntrada(UsuarioDados):
    """Cadastro de um usuário novo pelo administrador, já com a senha inicial."""

    senha: str

    @field_validator("senha")
    @classmethod
    def confere_senha(cls, valor: str) -> str:
        return senha_valida(valor)


class UsuarioEdicao(UsuarioDados):
    """Edição pelo administrador. A senha muda por outra rota."""

    ativo: bool


class NovaSenha(BaseModel):
    """Senha definida pelo administrador para outro usuário."""

    senha: str

    @field_validator("senha")
    @classmethod
    def confere_senha(cls, valor: str) -> str:
        return senha_valida(valor)


class TrocaDeSenha(BaseModel):
    """Troca da própria senha, confirmando a senha atual."""

    senha_atual: str = Field(min_length=1, max_length=SENHA_MAXIMA)
    nova_senha: str

    @field_validator("nova_senha")
    @classmethod
    def confere_senha(cls, valor: str) -> str:
        return senha_valida(valor)
