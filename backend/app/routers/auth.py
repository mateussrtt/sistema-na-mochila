from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.acesso import UsuarioLogado
from app.core.seguranca import criar_token, senha_confere
from app.db.session import get_db
from app.models import Usuario
from app.schemas.usuario import LoginEntrada, LoginResposta, UsuarioLeitura

router = APIRouter(prefix="/auth", tags=["login"])

Banco = Annotated[Session, Depends(get_db)]

# A mesma mensagem para e-mail inexistente, senha errada ou usuário desativado,
# para não revelar quais e-mails estão cadastrados
LOGIN_INVALIDO = "E-mail ou senha incorretos"


@router.post("/login", response_model=LoginResposta)
def entrar(dados: LoginEntrada, db: Banco) -> dict:
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados.email))
    senha_ok = senha_confere(dados.senha, usuario.senha_hash if usuario else None)
    if usuario is None or not senha_ok or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_INVALIDO)
    return {"token": criar_token(usuario.id), "usuario": usuario}


@router.get("/eu", response_model=UsuarioLeitura)
def eu(usuario: UsuarioLogado) -> Usuario:
    """Dados de quem está logado. A tela usa para montar o menu do perfil."""
    return usuario
