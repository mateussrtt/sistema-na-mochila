from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.acesso import SO_ADMIN, UsuarioLogado
from app.core.seguranca import gerar_hash
from app.db.session import get_db
from app.models import Usuario
from app.schemas.comum import ID_MAXIMO
from app.schemas.usuario import NovaSenha, UsuarioEdicao, UsuarioEntrada, UsuarioLeitura

# Só o administrador cadastra e altera usuários (RF03, RN13)
router = APIRouter(prefix="/usuarios", tags=["usuários"], dependencies=[SO_ADMIN])

Banco = Annotated[Session, Depends(get_db)]
UsuarioId = Annotated[int, Path(gt=0, le=ID_MAXIMO)]

EMAIL_EM_USO = "Já existe um usuário com este e-mail"
NAO_SE_DESATIVA = "Você não pode desativar o seu próprio usuário"
NAO_MUDA_O_PROPRIO_PERFIL = "Você não pode mudar o seu próprio perfil"


def busca_usuario(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    return usuario


def email_em_uso(db: Session, email: str, menos_o_id: int | None = None) -> bool:
    consulta = select(Usuario.id).where(Usuario.email == email)
    if menos_o_id is not None:
        consulta = consulta.where(Usuario.id != menos_o_id)
    return db.scalar(consulta) is not None


def salva(db: Session) -> None:
    """Grava no banco. Se dois cadastros com o mesmo e-mail chegarem juntos, um vira 409."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_EM_USO) from None


@router.get("", response_model=list[UsuarioLeitura])
def listar(db: Banco) -> list[Usuario]:
    """Lista os usuários: primeiro os ativos, em ordem alfabética."""
    return list(db.scalars(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)))


@router.post("", response_model=UsuarioLeitura, status_code=status.HTTP_201_CREATED)
def cadastrar(dados: UsuarioEntrada, db: Banco) -> Usuario:
    if email_em_uso(db, dados.email):
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_EM_USO)
    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        perfil=dados.perfil,
        senha_hash=gerar_hash(dados.senha),
    )
    db.add(usuario)
    salva(db)
    return usuario


@router.get("/{usuario_id}", response_model=UsuarioLeitura)
def consultar(usuario_id: UsuarioId, db: Banco) -> Usuario:
    return busca_usuario(db, usuario_id)


@router.put("/{usuario_id}", response_model=UsuarioLeitura)
def editar(
    usuario_id: UsuarioId, dados: UsuarioEdicao, db: Banco, quem_edita: UsuarioLogado
) -> Usuario:
    """Altera nome, e-mail, perfil e situação. Nada é apagado: desativar tira o acesso."""
    usuario = busca_usuario(db, usuario_id)
    # O administrador não pode se trancar fora do sistema. Como ele não muda o próprio
    # perfil nem se desativa, sempre sobra pelo menos um administrador ativo.
    if usuario.id == quem_edita.id:
        if not dados.ativo:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NAO_SE_DESATIVA)
        if dados.perfil != usuario.perfil:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NAO_MUDA_O_PROPRIO_PERFIL)
    if email_em_uso(db, dados.email, menos_o_id=usuario.id):
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_EM_USO)

    for campo, valor in dados.model_dump().items():
        setattr(usuario, campo, valor)
    salva(db)
    return usuario


@router.patch("/{usuario_id}/senha", response_model=UsuarioLeitura)
def redefinir_senha(usuario_id: UsuarioId, dados: NovaSenha, db: Banco) -> Usuario:
    """O administrador define uma nova senha, por exemplo quando alguém esquece a sua."""
    usuario = busca_usuario(db, usuario_id)
    usuario.senha_hash = gerar_hash(dados.senha)
    db.commit()
    return usuario
