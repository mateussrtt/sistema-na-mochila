from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core import lancamentos, tempo
from app.core.acesso import LOGADO, PODE_EDITAR, SO_ADMIN, UsuarioLogado
from app.db.session import get_db
from app.models import CategoriaReceita, Receita
from app.routers.mensalidades import mes_do_filtro
from app.schemas.cancelamento import cancelamento_de
from app.schemas.comum import ID_MAXIMO, termo_de_busca
from app.schemas.mensalidade import MotivoEntrada
from app.schemas.receita import (
    CategoriaReceitaLeitura,
    ReceitaCorrecao,
    ReceitaEntrada,
    ReceitaLeitura,
)

# Todas as rotas exigem login. Registrar receita exige perfil de operador ou administrador;
# cancelar e corrigir, só administrador (RN13)
router = APIRouter(prefix="/receitas", tags=["receitas"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]


def para_leitura(receita: Receita, substituida_por_id: int | None = None) -> ReceitaLeitura:
    return ReceitaLeitura(
        id=receita.id,
        data_receita=receita.data_receita,
        valor=receita.valor,
        categoria=CategoriaReceitaLeitura.model_validate(receita.categoria),
        descricao=receita.descricao,
        origem=receita.origem,
        registrado_por=receita.criado_por.nome,
        registrado_em=receita.criado_em,
        cancelamento=cancelamento_de(receita),
        substitui_id=receita.substitui_id,
        substituida_por_id=substituida_por_id,
    )


def busca_categoria_ativa(db: Session, categoria_id: int) -> CategoriaReceita:
    """Confere a categoria da receita (RN08): ela precisa existir e estar ativa.

    A linha fica travada para leitura até o fim: desativar a categoria ao mesmo tempo não deixa
    passar uma receita nova nela.
    """
    categoria = db.scalar(
        select(CategoriaReceita)
        .where(CategoriaReceita.id == categoria_id)
        .with_for_update(read=True)
    )
    if categoria is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Categoria não encontrada")
    if not categoria.ativo:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Categoria inativa não recebe receitas. Reative a categoria antes.",
        )
    return categoria


@router.get("", response_model=list[ReceitaLeitura])
def listar(
    db: Banco,
    mes: Annotated[str | None, Query(max_length=10)] = None,
    categoria_id: Annotated[int | None, Query(gt=0, le=ID_MAXIMO)] = None,
    busca: str | None = None,
) -> list[ReceitaLeitura]:
    """Lista as receitas da mais recente para a mais antiga.

    `mes` usa o formato AAAA-MM (vazio = todos os meses). A busca procura em quem pagou
    (origem) e na descrição.
    """
    consulta = (
        select(Receita)
        .options(
            joinedload(Receita.categoria),
            joinedload(Receita.criado_por),
            joinedload(Receita.cancelado_por),
        )
        .order_by(Receita.data_receita.desc(), Receita.id.desc())
    )
    primeiro_dia = mes_do_filtro(mes)
    if primeiro_dia is not None:
        proximo_mes = tempo.mes_seguinte(primeiro_dia)
        consulta = consulta.where(
            Receita.data_receita >= primeiro_dia, Receita.data_receita < proximo_mes
        )
    if categoria_id is not None:
        consulta = consulta.where(Receita.categoria_id == categoria_id)
    termo = termo_de_busca(busca)
    if termo:
        # autoescape: "%" e "_" digitados na busca valem como texto, não como curinga do SQL
        consulta = consulta.where(
            Receita.descricao.icontains(termo, autoescape=True)
            | Receita.origem.icontains(termo, autoescape=True)
        )
    lista = list(db.scalars(consulta))
    corrigidas = lancamentos.substitutos(db, Receita, [d.id for d in lista])
    return [para_leitura(d, corrigidas.get(d.id)) for d in lista]


@router.post(
    "",
    response_model=ReceitaLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[PODE_EDITAR],
)
def registrar(dados: ReceitaEntrada, db: Banco, usuario: UsuarioLogado) -> ReceitaLeitura:
    """Registra uma receita além das mensalidades (RF18). Guarda quem registrou e quando (RF26).

    Valor maior que zero, data que não seja futura (RN09), categoria ativa e origem (RN08).
    Uma receita errada não se apaga (RN12): a correção é o cancelamento com motivo, em outra
    etapa.
    """
    categoria = busca_categoria_ativa(db, dados.categoria_id)
    receita = Receita(
        data_receita=dados.data_receita,
        valor=dados.valor,
        categoria_id=categoria.id,
        descricao=dados.descricao,
        origem=dados.origem,
        criado_por_id=usuario.id,
    )
    db.add(receita)
    db.commit()
    return para_leitura(receita)


NAO_ENCONTRADA = "Receita não encontrada"
JA_CANCELADA = "Esta receita já está cancelada"


@router.patch("/{receita_id}/cancelar", response_model=ReceitaLeitura, dependencies=[SO_ADMIN])
def cancelar(
    receita_id: Annotated[int, Path(gt=0, le=ID_MAXIMO)],
    dados: MotivoEntrada,
    db: Banco,
    usuario: UsuarioLogado,
) -> ReceitaLeitura:
    """Cancela a receita lançada errada, com o motivo (RF17). Nada é apagado (RN12): ela continua
    na lista, marcada como cancelada, e sai dos totais.
    """
    receita = lancamentos.travar(db, Receita, receita_id, NAO_ENCONTRADA)
    if receita.cancelado_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, JA_CANCELADA)
    lancamentos.marcar_cancelado(receita, dados.motivo, usuario)
    db.commit()
    db.refresh(receita)
    return para_leitura(receita, lancamentos.substitutos(db, Receita, [receita.id]).get(receita.id))


@router.post(
    "/{receita_id}/corrigir",
    response_model=ReceitaLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[SO_ADMIN],
)
def corrigir(
    receita_id: Annotated[int, Path(gt=0, le=ID_MAXIMO)],
    dados: ReceitaCorrecao,
    db: Banco,
    usuario: UsuarioLogado,
) -> ReceitaLeitura:
    """Corrige uma receita: cancela a errada com o motivo e registra a certa no lugar (RF17).

    As duas coisas acontecem juntas: ou as duas, ou nenhuma. A nova receita aponta para a que ela
    substitui, e quem corrigiu fica registrado nas duas (RF26).
    """
    errada = lancamentos.travar(db, Receita, receita_id, NAO_ENCONTRADA)
    if errada.cancelado_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, JA_CANCELADA)
    categoria = busca_categoria_ativa(db, dados.categoria_id)
    certa = Receita(
        data_receita=dados.data_receita,
        valor=dados.valor,
        categoria_id=categoria.id,
        descricao=dados.descricao,
        origem=dados.origem,
        criado_por_id=usuario.id,
        substitui_id=errada.id,
    )
    lancamentos.marcar_cancelado(errada, dados.motivo, usuario)
    db.add(certa)
    db.commit()
    return para_leitura(certa)
