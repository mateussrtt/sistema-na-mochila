from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.acesso import LOGADO, PODE_EDITAR
from app.db.session import get_db
from app.models import Padrinho
from app.schemas.comum import ID_MAXIMO, termo_de_busca
from app.schemas.padrinho import PadrinhoEntrada, PadrinhoLeitura

# Todas as rotas exigem login. As que alteram dados exigem perfil de operador ou administrador
router = APIRouter(prefix="/padrinhos", tags=["padrinhos"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]
PadrinhoId = Annotated[int, Path(gt=0, le=ID_MAXIMO)]

CNPJ_REPETIDO = "Já existe um padrinho com este CNPJ"


def busca_padrinho(db: Session, padrinho_id: int) -> Padrinho:
    padrinho = db.get(Padrinho, padrinho_id)
    if padrinho is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Padrinho não encontrado")
    return padrinho


def exige_cnpj_livre(db: Session, cnpj: str | None, ignorar_id: int | None = None) -> None:
    """Recusa um CNPJ que já é de outro padrinho. Sem CNPJ, não há o que conferir."""
    if cnpj is None:
        return
    consulta = select(Padrinho.id).where(Padrinho.cnpj == cnpj)
    if ignorar_id is not None:
        consulta = consulta.where(Padrinho.id != ignorar_id)
    if db.scalar(consulta) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, CNPJ_REPETIDO)


def grava(db: Session) -> None:
    """Confirma a gravação. Dois pedidos ao mesmo tempo com o mesmo CNPJ viram 409, não 500.

    A conferência de `exige_cnpj_livre` acontece antes e é a que dá a mensagem no caso normal;
    esta cobre a corrida entre duas requisições, que só o índice único do banco consegue barrar.
    """
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        if "uq_padrinhos_cnpj" in str(erro.orig):
            raise HTTPException(status.HTTP_409_CONFLICT, CNPJ_REPETIDO) from None
        raise


@router.get("", response_model=list[PadrinhoLeitura])
def listar(
    db: Banco,
    busca: str | None = None,
    situacao: Literal["ativos", "inativos", "todos"] = "ativos",
) -> list[Padrinho]:
    """Lista os padrinhos em ordem alfabética. A busca procura no nome e no contato."""
    consulta = select(Padrinho).order_by(Padrinho.nome, Padrinho.id)
    if situacao != "todos":
        consulta = consulta.where(Padrinho.ativo.is_(situacao == "ativos"))
    termo = termo_de_busca(busca)
    if termo:
        # autoescape: "%" e "_" digitados na busca valem como texto, não como curinga do SQL
        consulta = consulta.where(
            or_(
                Padrinho.nome.icontains(termo, autoescape=True),
                Padrinho.contato.icontains(termo, autoescape=True),
            )
        )
    return list(db.scalars(consulta))


@router.post(
    "",
    response_model=PadrinhoLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[PODE_EDITAR],
)
def cadastrar(dados: PadrinhoEntrada, db: Banco) -> Padrinho:
    exige_cnpj_livre(db, dados.cnpj)
    padrinho = Padrinho(**dados.model_dump())
    db.add(padrinho)
    grava(db)
    return padrinho


@router.get("/{padrinho_id}", response_model=PadrinhoLeitura)
def consultar(padrinho_id: PadrinhoId, db: Banco) -> Padrinho:
    return busca_padrinho(db, padrinho_id)


@router.put("/{padrinho_id}", response_model=PadrinhoLeitura, dependencies=[PODE_EDITAR])
def editar(padrinho_id: PadrinhoId, dados: PadrinhoEntrada, db: Banco) -> Padrinho:
    """Edita o padrinho. Para inativar ou reativar, envie "ativo": false ou true.

    O padrinho nunca é apagado: inativar só o tira das listas de quem está em atividade.
    """
    padrinho = busca_padrinho(db, padrinho_id)
    exige_cnpj_livre(db, dados.cnpj, ignorar_id=padrinho.id)
    for campo, valor in dados.model_dump().items():
        setattr(padrinho, campo, valor)
    grava(db)
    return padrinho
