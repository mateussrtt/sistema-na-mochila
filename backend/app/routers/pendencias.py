from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import tempo
from app.core.acesso import LOGADO
from app.db.session import get_db
from app.models import Aluno, Matricula, Mensalidade, Responsavel, aluno_responsavel, esta_atrasada
from app.routers.mensalidades import mes_do_filtro
from app.schemas.pendencia import (
    AlunoEmAtraso,
    ContatoDoResponsavel,
    GrupoEmAtraso,
    MensalidadeEmAtraso,
    Pendencias,
    ResumoDePendencias,
)

# Só leitura, aberta a qualquer perfil logado (UC02)
router = APIRouter(prefix="/pendencias", tags=["pendências"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]

ZERO = Decimal("0.00")


@router.get("", response_model=Pendencias)
def listar(
    db: Banco,
    mes: Annotated[str | None, Query(max_length=10)] = None,
) -> Pendencias:
    """Mensalidades em atraso, agrupadas pelos responsáveis dos alunos (RF12).

    Atrasada é a mensalidade pendente cujo vencimento já passou: no dia 10 ainda não está
    atrasada, a partir do dia 11 está (RN07). Paga, isenta e cancelada nunca entram.

    - `mes` (AAAA-MM) mostra só as mensalidades daquele mês; sem ele, todos os meses.
    - Cada aluno em atraso aparece **uma vez só**. Alunos com exatamente os mesmos
      responsáveis (por exemplo, irmãos) ficam no mesmo grupo, com os responsáveis listados
      juntos. Assim nenhuma cobrança parece repetida e a soma dos grupos é o total em aberto.
    - Aluno inativo continua na lista enquanto deve: inativar não perdoa a dívida.
    """
    hoje = tempo.hoje()
    consulta = (
        select(
            Mensalidade.id,
            Mensalidade.competencia,
            Mensalidade.valor,
            Mensalidade.data_vencimento,
            Aluno.id,
            Aluno.nome,
            Aluno.ativo,
            Responsavel.id,
            Responsavel.nome,
            Responsavel.telefone,
            Responsavel.email,
        )
        .join(Matricula, Mensalidade.matricula_id == Matricula.id)
        .join(Aluno, Matricula.aluno_id == Aluno.id)
        # "outer": um aluno sem responsável (não deveria existir, RN01) não pode sumir da lista
        .outerjoin(aluno_responsavel, aluno_responsavel.c.aluno_id == Aluno.id)
        .outerjoin(Responsavel, Responsavel.id == aluno_responsavel.c.responsavel_id)
        # A cobrança da empresa tem a tela dela: aluno apadrinhado não deve ao responsável
        .where(esta_atrasada(hoje), Mensalidade.cobranca_id.is_(None))
    )
    primeiro_dia = mes_do_filtro(mes)
    if primeiro_dia is not None:
        consulta = consulta.where(Mensalidade.competencia == primeiro_dia)

    alunos: dict[int, AlunoEmAtraso] = {}
    responsaveis_do_aluno: dict[int, dict[int, ContatoDoResponsavel]] = {}
    atraso_do_aluno: dict[int, int] = {}
    mensalidades_vistas: set[int] = set()

    # A consulta devolve uma linha por mensalidade e por responsável do aluno
    for linha in db.execute(consulta):
        (m_id, competencia, valor, vencimento, a_id, a_nome, a_ativo) = linha[:7]
        (r_id, r_nome, r_telefone, r_email) = linha[7:]
        atraso = (hoje - vencimento).days

        aluno = alunos.get(a_id)
        if aluno is None:
            aluno = alunos[a_id] = AlunoEmAtraso(
                id=a_id, nome=a_nome, ativo=a_ativo, total=ZERO, mensalidades=[]
            )
            responsaveis_do_aluno[a_id] = {}
        if m_id not in mensalidades_vistas:
            mensalidades_vistas.add(m_id)
            aluno.mensalidades.append(
                MensalidadeEmAtraso(
                    id=m_id,
                    competencia=competencia,
                    valor=valor,
                    data_vencimento=vencimento,
                    dias_em_atraso=atraso,
                )
            )
            aluno.total += valor
            atraso_do_aluno[a_id] = max(atraso_do_aluno.get(a_id, 0), atraso)
        if r_id is not None:
            responsaveis_do_aluno[a_id][r_id] = ContatoDoResponsavel(
                id=r_id, nome=r_nome, telefone=r_telefone, email=r_email
            )

    # Alunos com exatamente os mesmos responsáveis formam um grupo só
    grupos: dict[tuple[int, ...], GrupoEmAtraso] = {}
    for a_id, aluno in alunos.items():
        aluno.mensalidades.sort(key=lambda m: (m.competencia, m.id))
        contatos = sorted(responsaveis_do_aluno[a_id].values(), key=lambda c: (c.nome, c.id))
        chave = tuple(sorted(c.id for c in contatos))
        grupo = grupos.get(chave)
        if grupo is None:
            grupo = grupos[chave] = GrupoEmAtraso(
                responsaveis=contatos, alunos=[], total=ZERO, maior_atraso=0
            )
        grupo.alunos.append(aluno)
        grupo.total += aluno.total
        grupo.maior_atraso = max(grupo.maior_atraso, atraso_do_aluno[a_id])

    lista = list(grupos.values())
    for grupo in lista:
        grupo.alunos.sort(key=lambda a: (a.nome, a.id))
    # Quem está há mais tempo em atraso vem primeiro; depois por nome dos responsáveis
    lista.sort(
        key=lambda g: (
            -g.maior_atraso,
            [c.nome for c in g.responsaveis],
            [c.id for c in g.responsaveis],
        )
    )

    return Pendencias(
        mes=primeiro_dia,
        resumo=ResumoDePendencias(
            responsaveis=len({c.id for g in lista for c in g.responsaveis}),
            alunos=len(alunos),
            mensalidades=len(mensalidades_vistas),
            total_em_aberto=sum((a.total for a in alunos.values()), ZERO),
        ),
        grupos=lista,
    )
