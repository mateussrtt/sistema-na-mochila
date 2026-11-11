from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.acesso import LOGADO, PODE_EDITAR
from app.db.session import get_db
from app.models import CategoriaDespesa
from app.schemas.comum import ID_MAXIMO, termo_de_busca
from app.schemas.despesa import CategoriaDespesaEntrada, CategoriaDespesaLeitura

# Todas as rotas exigem login. As que alteram dados exigem perfil de operador ou administrador
router = APIRouter(
    prefix="/categorias-despesa", tags=["categorias de despesa"], dependencies=[LOGADO]
)

Banco = Annotated[Session, Depends(get_db)]
CategoriaId = Annotated[int, Path(gt=0, le=ID_MAXIMO)]

NOME_REPETIDO = "Já existe uma categoria com este nome"


def busca_categoria(db: Session, categoria_id: int) -> CategoriaDespesa:
    categoria = db.get(CategoriaDespesa, categoria_id)
    if categoria is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoria não encontrada")
    return categoria


def exige_nome_livre(db: Session, nome: str, ignorar_id: int | None = None) -> None:
    """Recusa um nome que já é de outra categoria, sem diferenciar maiúsculas de minúsculas."""
    consulta = select(CategoriaDespesa.id).where(
        func.lower(CategoriaDespesa.nome) == func.lower(nome)
    )
    if ignorar_id is not None:
        consulta = consulta.where(CategoriaDespesa.id != ignorar_id)
    if db.scalar(consulta) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, NOME_REPETIDO)


def grava(db: Session) -> None:
    """Confirma a gravação. Dois pedidos ao mesmo tempo com o mesmo nome viram 409, não 500.

    A conferência de `exige_nome_livre` acontece antes e é a que dá a mensagem no caso normal;
    esta cobre a corrida entre duas requisições, que só o índice único do banco consegue barrar.
    """
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        if "uq_categorias_despesa_nome" in str(erro.orig):
            raise HTTPException(status.HTTP_409_CONFLICT, NOME_REPETIDO) from None
        raise


@router.get("", response_model=list[CategoriaDespesaLeitura])
def listar(
    db: Banco,
    busca: str | None = None,
    situacao: Literal["ativos", "inativos", "todos"] = "ativos",
) -> list[CategoriaDespesaLeitura]:
    """Lista as categorias em ordem alfabética. A busca procura no nome."""
    consulta = select(CategoriaDespesa).order_by(CategoriaDespesa.nome, CategoriaDespesa.id)
    if situacao != "todos":
        consulta = consulta.where(CategoriaDespesa.ativo.is_(situacao == "ativos"))
    termo = termo_de_busca(busca)
    if termo:
        # autoescape: "%" e "_" digitados na busca valem como texto, não como curinga do SQL
        consulta = consulta.where(CategoriaDespesa.nome.icontains(termo, autoescape=True))
    return [CategoriaDespesaLeitura.model_validate(c) for c in db.scalars(consulta)]


@router.post(
    "",
    response_model=CategoriaDespesaLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[PODE_EDITAR],
)
def cadastrar(dados: CategoriaDespesaEntrada, db: Banco) -> CategoriaDespesaLeitura:
    exige_nome_livre(db, dados.nome)
    categoria = CategoriaDespesa(**dados.model_dump())
    db.add(categoria)
    grava(db)
    return CategoriaDespesaLeitura.model_validate(categoria)


@router.get("/{categoria_id}", response_model=CategoriaDespesaLeitura)
def consultar(categoria_id: CategoriaId, db: Banco) -> CategoriaDespesaLeitura:
    return CategoriaDespesaLeitura.model_validate(busca_categoria(db, categoria_id))


@router.put("/{categoria_id}", response_model=CategoriaDespesaLeitura, dependencies=[PODE_EDITAR])
def editar(
    categoria_id: CategoriaId, dados: CategoriaDespesaEntrada, db: Banco
) -> CategoriaDespesaLeitura:
    """Edita a categoria. Para desativar ou reativar, envie "ativo": false ou true.

    A categoria nunca é apagada: desativar só a tira da lista de quem lança despesas novas. As
    despesas que já estão nela continuam no histórico.
    """
    categoria = busca_categoria(db, categoria_id)
    exige_nome_livre(db, dados.nome, ignorar_id=categoria.id)
    for campo, valor in dados.model_dump().items():
        setattr(categoria, campo, valor)
    grava(db)
    return CategoriaDespesaLeitura.model_validate(categoria)
