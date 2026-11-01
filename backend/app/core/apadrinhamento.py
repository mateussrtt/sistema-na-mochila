"""Inclusão das mensalidades dos alunos apadrinhados na cobrança da empresa (RN16, RN18)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Cobranca, Mensalidade, Padrinho, StatusCobranca, StatusMensalidade


class Apadrinhado(NamedTuple):
    """O que a geração precisa saber de uma matrícula apadrinhada em vigor no mês."""

    matricula_id: int
    padrinho_id: int
    valor: Decimal


def vencimento_sugerido(competencia: date, padrinho: Padrinho) -> date:
    """O dia combinado com a empresa, dentro do mês da cobrança."""
    return competencia.replace(day=padrinho.dia_vencimento)


def limite_de_emissao(competencia: date, padrinho: Padrinho) -> date | None:
    """O dia até o qual a nota deve ser emitida, se a empresa combinou um."""
    if padrinho.emitir_ate_dia is None:
        return None
    return competencia.replace(day=padrinho.emitir_ate_dia)


def cobranca_aberta(
    db: Session, padrinho: Padrinho, competencia: date, valor: Decimal, usuario_id: int
) -> tuple[Cobranca, bool]:
    """A cobrança "a emitir" da empresa no mês, travada para quem a usa. Cria se não existir.

    O banco só deixa uma aberta por empresa e mês, então dois geradores ao mesmo tempo acabam na
    mesma cobrança. Se ela for emitida no meio do caminho, tenta de novo: quem chegou depois da
    nota forma uma cobrança complementar.
    """
    while True:
        criadas = db.execute(
            insert(Cobranca)
            .values(
                padrinho_id=padrinho.id,
                competencia=competencia,
                valor=valor,
                status=StatusCobranca.A_EMITIR,
                data_vencimento=vencimento_sugerido(competencia, padrinho),
                limite_emissao=limite_de_emissao(competencia, padrinho),
                criado_por_id=usuario_id,
            )
            .on_conflict_do_nothing(
                index_elements=["padrinho_id", "competencia"],
                index_where=text("status = 'a_emitir'"),
            )
            .returning(Cobranca.id)
        ).all()
        aberta = db.scalar(
            select(Cobranca)
            .where(
                Cobranca.padrinho_id == padrinho.id,
                Cobranca.competencia == competencia,
                Cobranca.status == StatusCobranca.A_EMITIR,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if aberta is not None:
            return aberta, bool(criadas)


def incluir_apadrinhados(
    db: Session, apadrinhados: list[Apadrinhado], competencia: date, usuario_id: int
) -> tuple[int, int]:
    """Cria a mensalidade de cada apadrinhado dentro da cobrança aberta da empresa.

    Devolve quantos alunos entraram e quantas cobranças novas nasceram. O valor da cobrança é
    sempre a soma das mensalidades dela, recalculada com a cobrança travada: gerar de novo, ou
    dois operadores gerarem juntos, nunca duplica nem erra a soma. Quem não foi incluído porque
    outra geração chegou primeiro não conta aqui.
    """
    por_padrinho: dict[int, list[Apadrinhado]] = defaultdict(list)
    for apadrinhado in apadrinhados:
        por_padrinho[apadrinhado.padrinho_id].append(apadrinhado)
    if not por_padrinho:
        return 0, 0

    padrinhos = {p.id: p for p in db.scalars(select(Padrinho).where(Padrinho.id.in_(por_padrinho)))}
    incluidos = 0
    novas = 0
    # Sempre na mesma ordem, para dois geradores nunca esperarem um pelo outro (impasse)
    for padrinho_id in sorted(por_padrinho):
        itens = por_padrinho[padrinho_id]
        cobranca, nasceu = cobranca_aberta(
            db,
            padrinhos[padrinho_id],
            competencia,
            sum((i.valor for i in itens), Decimal("0.00")),
            usuario_id,
        )
        inseridas = db.execute(
            insert(Mensalidade)
            .values(
                [
                    {
                        "matricula_id": i.matricula_id,
                        "competencia": competencia,
                        "valor": i.valor,
                        "data_vencimento": cobranca.data_vencimento,
                        "status": StatusMensalidade.PENDENTE,
                        "criado_por_id": usuario_id,
                        "cobranca_id": cobranca.id,
                    }
                    for i in itens
                ]
            )
            .on_conflict_do_nothing(constraint="uq_mensalidades_matricula_competencia")
            .returning(Mensalidade.id)
        ).all()
        total = db.scalar(
            select(func.sum(Mensalidade.valor)).where(Mensalidade.cobranca_id == cobranca.id)
        )
        if total is None:
            # Só acontece se outra geração incluiu os mesmos alunos um instante antes e esta
            # cobrança acabou de nascer vazia: não há o que guardar
            db.delete(cobranca)
            continue
        cobranca.valor = total
        incluidos += len(inseridas)
        novas += int(nasceu)
    return incluidos, novas
