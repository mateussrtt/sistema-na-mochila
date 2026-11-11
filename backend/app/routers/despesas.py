from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.acesso import LOGADO, PODE_EDITAR, UsuarioLogado
from app.db.session import get_db
from app.models import CategoriaDespesa, Despesa
from app.routers.mensalidades import mes_do_filtro
from app.schemas.comum import ID_MAXIMO, termo_de_busca
from app.schemas.despesa import CategoriaDespesaLeitura, DespesaEntrada, DespesaLeitura

# Todas as rotas exigem login. Registrar despesa exige perfil de operador ou administrador
router = APIRouter(prefix="/despesas", tags=["despesas"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]


def para_leitura(despesa: Despesa) -> DespesaLeitura:
    return DespesaLeitura(
        id=despesa.id,
        data_despesa=despesa.data_despesa,
        valor=despesa.valor,
        categoria=CategoriaDespesaLeitura.model_validate(despesa.categoria),
        descricao=despesa.descricao,
        favorecido=despesa.favorecido,
        registrado_por=despesa.criado_por.nome,
        registrado_em=despesa.criado_em,
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
        .options(joinedload(Despesa.categoria), joinedload(Despesa.criado_por))
        .order_by(Despesa.data_despesa.desc(), Despesa.id.desc())
    )
    primeiro_dia = mes_do_filtro(mes)
    if primeiro_dia is not None:
        proximo_mes = (
            primeiro_dia.replace(year=primeiro_dia.year + 1, month=1)
            if primeiro_dia.month == 12
            else primeiro_dia.replace(month=primeiro_dia.month + 1)
        )
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
    return [para_leitura(d) for d in db.scalars(consulta)]


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
