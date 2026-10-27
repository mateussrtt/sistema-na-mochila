"""Senhas e tokens de login."""

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITMO = "HS256"

# Argon2, o algoritmo recomendado hoje para guardar senhas
_hasher = PasswordHash.recommended()

# Usado quando o e-mail não existe, para o login demorar o mesmo tempo nos dois casos.
# Assim ninguém descobre quais e-mails estão cadastrados medindo o tempo da resposta.
_HASH_FALSO = _hasher.hash("senha-que-nao-existe")


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def senha_confere(senha: str, senha_hash: str | None) -> bool:
    if senha_hash is None:
        _hasher.verify(senha, _HASH_FALSO)
        return False
    return _hasher.verify(senha, senha_hash)


def criar_token(usuario_id: int, agora: datetime | None = None) -> str:
    """Token assinado com o id do usuário. Vale pelo número de horas da configuração."""
    config = get_settings()
    agora = agora or datetime.now(UTC)
    dados = {"sub": str(usuario_id), "exp": agora + timedelta(hours=config.horas_de_sessao)}
    return jwt.encode(dados, config.secret_key, algorithm=ALGORITMO)


def ler_token(token: str) -> int | None:
    """Devolve o id do usuário, ou None se o token for inválido ou estiver vencido."""
    try:
        dados = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITMO])
        return int(dados["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
