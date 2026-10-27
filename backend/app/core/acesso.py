"""Quem está logado e o que cada perfil pode fazer."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.seguranca import ler_token
from app.db.session import get_db
from app.models import Perfil, Usuario

_bearer = HTTPBearer(auto_error=False, description="Token recebido em /api/auth/login")


def _nao_autorizado(mensagem: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, mensagem, headers={"WWW-Authenticate": "Bearer"}
    )


def usuario_logado(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    """Lê o token do cabeçalho Authorization e devolve o usuário dono dele."""
    if credenciais is None:
        raise _nao_autorizado("Faça login para continuar")
    usuario_id = ler_token(credenciais.credentials)
    usuario = db.get(Usuario, usuario_id) if usuario_id is not None else None
    if usuario is None or not usuario.ativo:
        raise _nao_autorizado("Sua sessão expirou. Entre de novo.")
    return usuario


UsuarioLogado = Annotated[Usuario, Depends(usuario_logado)]


def exige_perfil(*perfis: Perfil) -> Callable[[Usuario], Usuario]:
    """Libera a rota só para os perfis informados."""

    def verifica(usuario: UsuarioLogado) -> Usuario:
        if usuario.perfil not in perfis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu perfil não pode fazer isso")
        return usuario

    return verifica


# Para usar em dependencies=[...] das rotas
LOGADO = Depends(usuario_logado)
PODE_EDITAR = Depends(exige_perfil(Perfil.ADMINISTRADOR, Perfil.OPERADOR))
SO_ADMIN = Depends(exige_perfil(Perfil.ADMINISTRADOR))
