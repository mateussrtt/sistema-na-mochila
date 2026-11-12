from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core import lancamentos, tempo
from app.core.acesso import LOGADO, PODE_EDITAR, SO_ADMIN, UsuarioLogado
from app.db.session import get_db
from app.models import CategoriaDespesa, Despesa
from app.routers.mensalidades import mes_do_filtro
from app.schemas.cancelamento import cancelamento_de
from app.schemas.comum import ID_MAXIMO, termo_de_busca
from app.schemas.despesa import (
    CategoriaDespesaLeitura,
    DespesaCorrecao,
    DespesaEntrada,
    DespesaLeitura,
)
from app.schemas.mensalidade import MotivoEntrada

# Todas as rotas exigem login. Registrar despesa exige perfil de operador ou administrador;
# cancelar e corrigir, só administrador (RN13)
router = APIRouter(prefix="/despesas", tags=["despesas"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]


def para_leitura(despesa: Despesa, substituida_por_id: int | None = None) -> DespesaLeitura:
    return DespesaLeitura(
        id=despesa.id,
        data_despesa=despesa.data_despesa,
        valor=despesa.valor,
        categoria=CategoriaDespesaLeitura.model_validate(despesa.categoria),
        descricao=despesa.descricao,
        favorecido=despesa.favorecido,
        registrado_por=despesa.criado_por.nome,
        registrado_em=despesa.criado_em,
        cancelamento=cancelamento_de(despesa),
        substitui_id=despesa.substitui_id,
        substituida_por_id=substituida_por_id,
    )


def busca_categoria_ativa(db: Session, categoria_id: int) -> CategoriaDespesa:
    """Confere a categoria da despesa (RN08): ela precisa existir e estar ativa.

    A linha fica travada para leitura até o fim: desativar a categoria ao mesmo tempo não deixa
    passar uma despesa nova nela.
    """
    categoria = db.scalar(
        select(CategoriaDespesa)
        .where(CategoriaDespesa.id == categoria_id)
        .with_for_update(read=True)
    )
    if categoria is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Categoria não encontrada")
    if not categoria.ativo:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Categoria inativa não recebe despesas. Reative a categoria antes.",
        )
    return categoria


@router.get("", response_model=list[DespesaLeitura])
def listar(
    db: Banco,
    mes: Annotated[str | None, Query(max_length=10)] = None,
    categoria_id: Annotated[int | None, Query(gt=0, le=ID_MAXIMO)] = None,
    busca: str | None = None,
) -> list[DespesaLeitura]:
    """Lista as despesas da mais recente para a mais antiga.

    `mes` usa o formato AAAA-MM (vazio = todos os meses). A busca procura no que foi comprado
    (descrição) e em para quem foi pago (favorecido).
    """
    consulta = (
        select(Despesa)
        .options(
            joinedload(Despesa.categoria),
            joinedload(Despesa.criado_por),
            joinedload(Despesa.cancelado_por),
        )
        .order_by(Despesa.data_despesa.desc(), Despesa.id.desc())
    )
    primeiro_dia = mes_do_filtro(mes)
    if primeiro_dia is not None:
        proximo_mes = tempo.mes_seguinte(primeiro_dia)
        consulta = consulta.where(
            Despesa.data_despesa >= primeiro_dia, Despesa.data_despesa < proximo_mes
        )
    if categoria_id is not None:
        consulta = consulta.where(Despesa.categoria_id == categoria_id)
    termo = termo_de_busca(busca)
    if termo:
        # autoescape: "%" e "_" digitados na busca valem como texto, não como curinga do SQL
        consulta = consulta.where(
            Despesa.descricao.icontains(termo, autoescape=True)
            | Despesa.favorecido.icontains(termo, autoescape=True)
        )
    lista = list(db.scalars(consulta))
    corrigidas = lancamentos.substitutos(db, Despesa, [d.id for d in lista])
    return [para_leitura(d, corrigidas.get(d.id)) for d in lista]


@router.post(
    "",
    response_model=DespesaLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[PODE_EDITAR],
)
def registrar(dados: DespesaEntrada, db: Banco, usuario: UsuarioLogado) -> DespesaLeitura:
    """Registra uma despesa (RF16). Guarda quem registrou e quando (RF26).

    Valor maior que zero, data que não seja futura (RN09) e categoria ativa (RN08). Uma despesa
    errada não se apaga (RN12): a correção é o cancelamento com motivo, em outra etapa.
    """
    categoria = busca_categoria_ativa(db, dados.categoria_id)
    despesa = Despesa(
        data_despesa=dados.data_despesa,
        valor=dados.valor,
        categoria_id=categoria.id,
        descricao=dados.descricao,
        favorecido=dados.favorecido,
        criado_por_id=usuario.id,
    )
    db.add(despesa)
    db.commit()
    return para_leitura(despesa)


NAO_ENCONTRADA = "Despesa não encontrada"
JA_CANCELADA = "Esta despesa já está cancelada"


@router.patch("/{despesa_id}/cancelar", response_model=DespesaLeitura, dependencies=[SO_ADMIN])
def cancelar(
    despesa_id: Annotated[int, Path(gt=0, le=ID_MAXIMO)],
    dados: MotivoEntrada,
    db: Banco,
    usuario: UsuarioLogado,
) -> DespesaLeitura:
    """Cancela a despesa lançada errada, com o motivo (RF17). Nada é apagado (RN12): ela continua
    na lista, marcada como cancelada, e sai dos totais.
    """
    despesa = lancamentos.travar(db, Despesa, despesa_id, NAO_ENCONTRADA)
    if despesa.cancelado_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, JA_CANCELADA)
    lancamentos.marcar_cancelado(despesa, dados.motivo, usuario)
    db.commit()
    db.refresh(despesa)
    return para_leitura(despesa, lancamentos.substitutos(db, Despesa, [despesa.id]).get(despesa.id))


@router.post(
    "/{despesa_id}/corrigir",
    response_model=DespesaLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[SO_ADMIN],
)
def corrigir(
    despesa_id: Annotated[int, Path(gt=0, le=ID_MAXIMO)],
    dados: DespesaCorrecao,
    db: Banco,
    usuario: UsuarioLogado,
) -> DespesaLeitura:
    """Corrige uma despesa: cancela a errada com o motivo e registra a certa no lugar (RF17).

    As duas coisas acontecem juntas: ou as duas, ou nenhuma. A nova despesa aponta para a que ela
    substitui, e quem corrigiu fica registrado nas duas (RF26).
    """
    errada = lancamentos.travar(db, Despesa, despesa_id, NAO_ENCONTRADA)
    if errada.cancelado_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, JA_CANCELADA)
    categoria = busca_categoria_ativa(db, dados.categoria_id)
    certa = Despesa(
        data_despesa=dados.data_despesa,
        valor=dados.valor,
        categoria_id=categoria.id,
        descricao=dados.descricao,
        favorecido=dados.favorecido,
        criado_por_id=usuario.id,
        substitui_id=errada.id,
    )
    lancamentos.marcar_cancelado(errada, dados.motivo, usuario)
    db.add(certa)
    db.commit()
    return para_leitura(certa)
