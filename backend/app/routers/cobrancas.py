from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, joinedload, selectinload

from app.core import lancamentos, tempo
from app.core.acesso import LOGADO, PODE_EDITAR, SO_ADMIN, UsuarioLogado
from app.db.session import get_db
from app.models import (
    Cobranca,
    Matricula,
    Mensalidade,
    Padrinho,
    PagamentoCobranca,
    StatusCobranca,
    StatusMensalidade,
    emissao_atrasada,
    situacao_da_cobranca,
)
from app.routers.mensalidades import mes_do_filtro
from app.schemas.cancelamento import cancelamento_de
from app.schemas.cobranca import (
    CobrancaLeitura,
    ItemDaCobranca,
    NotaEntrada,
    NotaLeitura,
    PadrinhoDaCobranca,
    PagamentoDaCobrancaCanceladoLeitura,
    PagamentoDaCobrancaEntrada,
    PagamentoDaCobrancaLeitura,
)
from app.schemas.comum import ID_MAXIMO
from app.schemas.matricula import AlunoResumo
from app.schemas.mensalidade import MotivoEntrada

# Todas as rotas exigem login. Registrar a nota e o pagamento exige operador ou administrador;
# cancelar, só administrador (RN13). A cobrança nasce quando as mensalidades do mês são geradas
router = APIRouter(prefix="/cobrancas", tags=["cobranças"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]
IdDaCobranca = Annotated[int, Path(gt=0, le=ID_MAXIMO)]

SituacaoDoFiltro = Literal[
    "todas", "a_emitir", "emissao_atrasada", "a_vencer", "atrasada", "paga", "cancelada"
]


def carregar(db: Session, consulta=None) -> list[Cobranca]:
    """Cobranças com tudo que a resposta mostra, em um número fixo de consultas."""
    consulta = select(Cobranca) if consulta is None else consulta
    return list(
        db.scalars(
            consulta.join(Cobranca.padrinho)
            .options(
                contains_eager(Cobranca.padrinho),
                joinedload(Cobranca.criado_por),
                joinedload(Cobranca.emitida_por),
                joinedload(Cobranca.cancelado_por),
                selectinload(Cobranca.mensalidades)
                .joinedload(Mensalidade.matricula)
                .joinedload(Matricula.aluno),
            )
            .order_by(Cobranca.competencia.desc(), Padrinho.nome, Cobranca.id)
            .execution_options(populate_existing=True)
        ).unique()
    )


def pagamentos_ativos(db: Session, cobrancas: list[Cobranca]) -> dict[int, PagamentoCobranca]:
    """O pagamento ativo de cada cobrança paga da lista, numa consulta só."""
    ids = [c.id for c in cobrancas if c.status == StatusCobranca.PAGA]
    if not ids:
        return {}
    pagamentos = db.scalars(
        select(PagamentoCobranca)
        .where(PagamentoCobranca.cobranca_id.in_(ids), PagamentoCobranca.cancelado_em.is_(None))
        .options(joinedload(PagamentoCobranca.criado_por))
    )
    return {p.cobranca_id: p for p in pagamentos}


def pagamentos_cancelados(db: Session, ids: list[int]) -> dict[int, list[PagamentoCobranca]]:
    """Os pagamentos cancelados de cada cobrança, do mais recente para o mais antigo (RF17)."""
    if not ids:
        return {}
    cancelados: dict[int, list[PagamentoCobranca]] = {}
    for pagamento in db.scalars(
        select(PagamentoCobranca)
        .where(PagamentoCobranca.cobranca_id.in_(ids), PagamentoCobranca.cancelado_em.is_not(None))
        .options(
            joinedload(PagamentoCobranca.criado_por), joinedload(PagamentoCobranca.cancelado_por)
        )
        .order_by(PagamentoCobranca.cancelado_em.desc(), PagamentoCobranca.id.desc())
    ):
        cancelados.setdefault(pagamento.cobranca_id, []).append(pagamento)
    return cancelados


def pagamento_para_leitura(pagamento: PagamentoCobranca) -> PagamentoDaCobrancaLeitura:
    return PagamentoDaCobrancaLeitura(
        data_pagamento=pagamento.data_pagamento,
        valor_pago=pagamento.valor_pago,
        forma_pagamento=pagamento.forma_pagamento,
        observacao=pagamento.observacao,
        registrado_por=pagamento.criado_por.nome,
        registrado_em=pagamento.criado_em,
    )


def para_leitura(
    cobranca: Cobranca,
    hoje: date,
    pagamento: PagamentoCobranca | None = None,
    cancelados: list[PagamentoCobranca] | None = None,
) -> CobrancaLeitura:
    situacao = situacao_da_cobranca(cobranca.status, cobranca.data_vencimento, hoje)
    atrasada = situacao == "atrasada"
    alunos = sorted(
        (
            ItemDaCobranca(
                mensalidade_id=m.id,
                matricula_id=m.matricula_id,
                aluno=AlunoResumo.model_validate(m.matricula.aluno),
                valor=m.valor,
            )
            for m in cobranca.mensalidades
        ),
        key=lambda i: (i.aluno.nome, i.mensalidade_id),
    )
    return CobrancaLeitura(
        id=cobranca.id,
        padrinho=PadrinhoDaCobranca(
            id=cobranca.padrinho.id, nome=cobranca.padrinho.nome, ativo=cobranca.padrinho.ativo
        ),
        competencia=cobranca.competencia,
        valor=cobranca.valor,
        status=cobranca.status,
        situacao=situacao,
        emissao_atrasada=emissao_atrasada(cobranca.status, cobranca.limite_emissao, hoje),
        limite_emissao=cobranca.limite_emissao,
        data_vencimento=cobranca.data_vencimento,
        dias_em_atraso=(hoje - cobranca.data_vencimento).days if atrasada else 0,
        alunos=alunos,
        gerada_por=cobranca.criado_por.nome,
        gerada_em=cobranca.criado_em,
        nota=(
            NotaLeitura(
                numero_nota=cobranca.numero_nota,
                data_emissao=cobranca.data_emissao,
                registrada_por=cobranca.emitida_por.nome,
                registrada_em=cobranca.emitida_em,
            )
            if cobranca.numero_nota is not None
            else None
        ),
        pagamento=pagamento_para_leitura(pagamento) if pagamento else None,
        pagamentos_cancelados=[
            PagamentoDaCobrancaCanceladoLeitura(
                **pagamento_para_leitura(c).model_dump(), cancelamento=cancelamento_de(c)
            )
            for c in cancelados or []
        ],
        motivo=cobranca.motivo_cancelamento,
        cancelada_por=cobranca.cancelado_por.nome if cobranca.cancelado_por else None,
        cancelada_em=cobranca.cancelado_em,
    )


def resposta(db: Session, cobranca_id: int) -> CobrancaLeitura:
    """A cobrança como está no banco agora, para devolver depois de uma alteração."""
    cobranca = carregar(db, select(Cobranca).where(Cobranca.id == cobranca_id))[0]
    return para_leitura(
        cobranca,
        tempo.hoje(),
        pagamentos_ativos(db, [cobranca]).get(cobranca_id),
        pagamentos_cancelados(db, [cobranca_id]).get(cobranca_id),
    )


@router.get("", response_model=list[CobrancaLeitura])
def listar(
    db: Banco,
    mes: Annotated[str | None, Query(max_length=10)] = None,
    situacao: SituacaoDoFiltro = "todas",
    padrinho_id: Annotated[int | None, Query(gt=0, le=ID_MAXIMO)] = None,
) -> list[CobrancaLeitura]:
    """Lista as cobranças das empresas, das mais recentes para as mais antigas (RF31).

    `mes` usa o formato AAAA-MM; sem ele, vêm todos os meses. A situação "a emitir" traz todas as
    notas que faltam, e "emissão atrasada" só as que já passaram do prazo da empresa.
    """
    hoje = tempo.hoje()
    consulta = select(Cobranca)
    primeiro_dia = mes_do_filtro(mes)
    if primeiro_dia is not None:
        consulta = consulta.where(Cobranca.competencia == primeiro_dia)
    if padrinho_id is not None:
        consulta = consulta.where(Cobranca.padrinho_id == padrinho_id)

    emitida = Cobranca.status == StatusCobranca.EMITIDA
    if situacao == "emissao_atrasada":
        consulta = consulta.where(
            Cobranca.status == StatusCobranca.A_EMITIR, Cobranca.limite_emissao < hoje
        )
    elif situacao == "a_vencer":
        consulta = consulta.where(emitida, Cobranca.data_vencimento >= hoje)
    elif situacao == "atrasada":
        consulta = consulta.where(emitida, Cobranca.data_vencimento < hoje)
    elif situacao != "todas":
        consulta = consulta.where(Cobranca.status == StatusCobranca(situacao))

    cobrancas = carregar(db, consulta)
    pagamentos = pagamentos_ativos(db, cobrancas)
    cancelados = pagamentos_cancelados(db, [c.id for c in cobrancas])
    return [para_leitura(c, hoje, pagamentos.get(c.id), cancelados.get(c.id)) for c in cobrancas]


@router.get("/{cobranca_id}", response_model=CobrancaLeitura)
def consultar(cobranca_id: IdDaCobranca, db: Banco) -> CobrancaLeitura:
    existe = db.scalar(select(Cobranca.id).where(Cobranca.id == cobranca_id))
    if existe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cobrança não encontrada")
    return resposta(db, cobranca_id)


def travar(db: Session, cobranca_id: int) -> Cobranca:
    """A cobrança com a linha travada até o fim: duas alterações simultâneas não passam juntas."""
    cobranca = db.scalar(
        select(Cobranca)
        .where(Cobranca.id == cobranca_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if cobranca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cobrança não encontrada")
    return cobranca


def erro_de_campo(campo: str, mensagem: str) -> RequestValidationError:
    """Mesmo formato dos outros erros de validação: uma lista com o campo e a mensagem."""
    return RequestValidationError(
        [{"type": "value_error", "loc": ("body", campo), "msg": mensagem, "input": None}]
    )


NOTA_REPETIDA = "Já existe uma cobrança com esse número de nota"


def numero_ja_usado(db: Session, numero: str, cobranca_id: int) -> bool:
    """Outra cobrança já tem esse número de nota (sem diferenciar maiúsculas de minúsculas)."""
    return (
        db.scalar(
            select(Cobranca.id).where(
                func.lower(Cobranca.numero_nota) == numero.lower(), Cobranca.id != cobranca_id
            )
        )
        is not None
    )


MOTIVO_DE_NAO_EMITIR = {
    StatusCobranca.PAGA: "Uma cobrança paga não pode ter a nota alterada",
    StatusCobranca.CANCELADA: "Uma cobrança cancelada não recebe nota",
}


@router.patch("/{cobranca_id}/nota", response_model=CobrancaLeitura, dependencies=[PODE_EDITAR])
def registrar_nota(
    cobranca_id: IdDaCobranca, dados: NotaEntrada, db: Banco, usuario: UsuarioLogado
) -> CobrancaLeitura:
    """Registra a nota fiscal emitida e deixa a cobrança "emitida" (RF31).

    - Informa o número, a data de emissão e o vencimento (a tela sugere o dia combinado com a
      empresa). O vencimento vale também para as mensalidades dos alunos.
    - Enquanto a cobrança não foi paga, a nota pode ser corrigida registrando de novo: vale o
      último registro, com quem fez e quando (RF26).
    - O número da nota não pode repetir em outra cobrança.
    """
    cobranca = travar(db, cobranca_id)
    if cobranca.status in MOTIVO_DE_NAO_EMITIR:
        raise HTTPException(status.HTTP_409_CONFLICT, MOTIVO_DE_NAO_EMITIR[cobranca.status])
    if dados.data_vencimento < cobranca.competencia:
        raise erro_de_campo("data_vencimento", "O vencimento não pode ser antes do mês da cobrança")
    if numero_ja_usado(db, dados.numero_nota, cobranca.id):
        raise HTTPException(status.HTTP_409_CONFLICT, NOTA_REPETIDA)

    cobranca.numero_nota = dados.numero_nota
    cobranca.data_emissao = dados.data_emissao
    cobranca.data_vencimento = dados.data_vencimento
    cobranca.emitida_por_id = usuario.id
    cobranca.emitida_em = func.now()
    cobranca.status = StatusCobranca.EMITIDA
    try:
        db.flush()
    except IntegrityError:
        # Outro pedido registrou o mesmo número de nota no mesmo instante
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, NOTA_REPETIDA) from None
    db.execute(
        update(Mensalidade)
        .where(Mensalidade.cobranca_id == cobranca.id)
        .values(data_vencimento=dados.data_vencimento)
    )
    db.commit()
    return resposta(db, cobranca_id)


MOTIVO_DE_NAO_RECEBER = {
    StatusCobranca.A_EMITIR: "Registre a nota da cobrança antes de registrar o pagamento",
    StatusCobranca.PAGA: "Esta cobrança já foi paga",
    StatusCobranca.CANCELADA: "Uma cobrança cancelada não recebe pagamento",
}


@router.post(
    "/{cobranca_id}/pagamento",
    response_model=CobrancaLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[PODE_EDITAR],
)
def registrar_pagamento(
    cobranca_id: IdDaCobranca,
    dados: PagamentoDaCobrancaEntrada,
    db: Banco,
    usuario: UsuarioLogado,
) -> CobrancaLeitura:
    """Registra o pagamento da empresa: a cobrança fica paga e as mensalidades dos alunos, quitadas.

    - Só a cobrança com a nota emitida recebe pagamento.
    - Se o valor pago for diferente do valor da cobrança, a observação é obrigatória (a tela pede
      a confirmação).
    - Guarda quem registrou e quando (RF26).
    """
    cobranca = travar(db, cobranca_id)
    if cobranca.status != StatusCobranca.EMITIDA:
        raise HTTPException(status.HTTP_409_CONFLICT, MOTIVO_DE_NAO_RECEBER[cobranca.status])
    if dados.valor_pago != cobranca.valor and dados.observacao is None:
        previsto = str(cobranca.valor).replace(".", ",")
        raise erro_de_campo(
            "observacao",
            f"O valor é diferente do cobrado (R$ {previsto}). Explique o motivo na observação",
        )

    db.add(
        PagamentoCobranca(
            cobranca_id=cobranca.id,
            data_pagamento=dados.data_pagamento,
            valor_pago=dados.valor_pago,
            forma_pagamento=dados.forma_pagamento,
            observacao=dados.observacao,
            criado_por_id=usuario.id,
        )
    )
    cobranca.status = StatusCobranca.PAGA
    db.execute(
        update(Mensalidade)
        .where(
            Mensalidade.cobranca_id == cobranca.id, Mensalidade.status == StatusMensalidade.PENDENTE
        )
        .values(status=StatusMensalidade.PAGA)
    )
    db.commit()
    return resposta(db, cobranca_id)


MOTIVO_DE_NAO_CANCELAR = {
    StatusCobranca.PAGA: "Uma cobrança paga não pode ser cancelada",
    StatusCobranca.CANCELADA: "Esta cobrança já está cancelada",
}


@router.patch("/{cobranca_id}/cancelar", response_model=CobrancaLeitura, dependencies=[SO_ADMIN])
def cancelar(
    cobranca_id: IdDaCobranca, dados: MotivoEntrada, db: Banco, usuario: UsuarioLogado
) -> CobrancaLeitura:
    """Cancela a cobrança (e as mensalidades dela), guardando motivo, autor e hora (RN12, RN13).

    Nada é apagado: a cobrança continua na lista, cancelada. A nota fiscal, se já foi emitida,
    precisa ser cancelada fora do sistema.
    """
    cobranca = travar(db, cobranca_id)
    if cobranca.status in MOTIVO_DE_NAO_CANCELAR:
        raise HTTPException(status.HTTP_409_CONFLICT, MOTIVO_DE_NAO_CANCELAR[cobranca.status])

    cobranca.status = StatusCobranca.CANCELADA
    cobranca.motivo_cancelamento = dados.motivo
    cobranca.cancelado_por_id = usuario.id
    cobranca.cancelado_em = func.now()
    db.execute(
        update(Mensalidade)
        .where(
            Mensalidade.cobranca_id == cobranca.id, Mensalidade.status == StatusMensalidade.PENDENTE
        )
        .values(
            status=StatusMensalidade.CANCELADA,
            motivo_alteracao=dados.motivo,
            alterado_por_id=usuario.id,
            alterado_em=func.now(),
        )
    )
    db.commit()
    return resposta(db, cobranca_id)


@router.patch(
    "/{cobranca_id}/pagamento/cancelar", response_model=CobrancaLeitura, dependencies=[SO_ADMIN]
)
def cancelar_pagamento(
    cobranca_id: IdDaCobranca, dados: MotivoEntrada, db: Banco, usuario: UsuarioLogado
) -> CobrancaLeitura:
    """Cancela o pagamento da empresa lançado errado (RF17).

    A cobrança volta a ficar emitida, esperando pagamento, e as mensalidades dos alunos dela
    deixam de estar quitadas. O pagamento não é apagado (RN12): fica no histórico da cobrança,
    com o motivo. Para corrigir, basta registrar o pagamento certo depois.
    """
    cobranca = travar(db, cobranca_id)
    pagamento = db.scalar(
        select(PagamentoCobranca).where(
            PagamentoCobranca.cobranca_id == cobranca.id, PagamentoCobranca.cancelado_em.is_(None)
        )
    )
    if cobranca.status != StatusCobranca.PAGA or pagamento is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esta cobrança não tem pagamento para cancelar"
        )

    lancamentos.marcar_cancelado(pagamento, dados.motivo, usuario)
    cobranca.status = StatusCobranca.EMITIDA
    # O pagamento da empresa quitou as mensalidades pendentes; agora elas voltam a pendentes
    db.execute(
        update(Mensalidade)
        .where(Mensalidade.cobranca_id == cobranca.id, Mensalidade.status == StatusMensalidade.PAGA)
        .values(status=StatusMensalidade.PENDENTE)
    )
    db.commit()
    return resposta(db, cobranca_id)
