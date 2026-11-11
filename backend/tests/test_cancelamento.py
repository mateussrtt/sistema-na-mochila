"""Cancelar e corrigir lançamentos (RF17): pagamentos, despesas e receitas.

Só o administrador cancela (RN13), sempre com motivo. Nada é apagado (RN12): o lançamento
cancelado continua visível, com quem cancelou e quando (RF26), e deixa de contar.
"""

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core import tempo
from app.models import Despesa, Mensalidade, Pagamento, Perfil, Receita
from tests import test_cobrancas as cobrancas

HOJE = date(2026, 11, 5)
MOTIVO = "Lançado em dobro por engano"


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Todos os testes rodam "em 5 de novembro de 2026", para não dependerem do dia em que rodam."""
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


# ======================= Pagamento de mensalidade =======================


@pytest.fixture
def paga(api, matricula) -> dict:
    """Uma mensalidade de novembro de R$ 150,00, já paga em 05/11."""
    matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    mensalidade = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()[0]
    resposta = api.post(
        f"/api/mensalidades/{mensalidade['id']}/pagamento",
        json={"data_pagamento": "2026-11-05", "valor_pago": "150.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def cancelar_pagamento(cliente, mensalidade_id, motivo=MOTIVO):
    return cliente.patch(
        f"/api/mensalidades/{mensalidade_id}/pagamento/cancelar", json={"motivo": motivo}
    )


def test_cancelar_pagamento_volta_a_mensalidade_para_pendente(api, paga):
    resposta = cancelar_pagamento(api, paga["id"])

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert (dados["status"], dados["situacao"]) == ("pendente", "a_vencer")
    assert dados["pagamento"] is None
    [cancelado] = dados["pagamentos_cancelados"]
    assert cancelado["valor_pago"] == "150.00"
    assert cancelado["cancelamento"]["motivo"] == MOTIVO
    assert cancelado["cancelamento"]["cancelado_por"].startswith("Usuário administrador")
    assert cancelado["cancelamento"]["cancelado_em"]


def test_o_pagamento_cancelado_continua_no_banco(api, db, paga):
    cancelar_pagamento(api, paga["id"])
    [pagamento] = db.scalars(select(Pagamento)).all()
    assert pagamento.cancelado_em is not None
    assert pagamento.motivo_cancelamento == MOTIVO


def test_depois_de_cancelar_registra_o_pagamento_certo(api, paga):
    cancelar_pagamento(api, paga["id"])
    resposta = api.post(
        f"/api/mensalidades/{paga['id']}/pagamento",
        json={
            "data_pagamento": "2026-11-04",
            "valor_pago": "150.00",
            "forma_pagamento": "dinheiro",
        },
    )

    assert resposta.status_code == 201, resposta.text
    dados = resposta.json()
    assert dados["status"] == "paga"
    assert dados["pagamento"]["forma_pagamento"] == "dinheiro"
    assert len(dados["pagamentos_cancelados"]) == 1


def test_a_lista_mostra_o_historico_de_pagamentos_cancelados(api, paga):
    cancelar_pagamento(api, paga["id"])
    lista = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    assert lista[0]["pagamentos_cancelados"][0]["cancelamento"]["motivo"] == MOTIVO


def test_mensalidade_com_pagamento_cancelado_volta_a_atrasar(api, paga, monkeypatch):
    cancelar_pagamento(api, paga["id"])
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 20))
    lista = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    assert lista[0]["situacao"] == "atrasada"


def test_mensalidade_sem_pagamento_nao_tem_o_que_cancelar(api, paga):
    cancelar_pagamento(api, paga["id"])
    resposta = cancelar_pagamento(api, paga["id"])
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Esta mensalidade não tem pagamento para cancelar"


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.CONSULTA])
def test_so_o_administrador_cancela_pagamento(api_como, paga, perfil):
    assert cancelar_pagamento(api_como(perfil), paga["id"]).status_code == 403


def test_cancelar_pagamento_exige_login(sem_login, paga):
    assert cancelar_pagamento(sem_login, paga["id"]).status_code == 401


@pytest.mark.parametrize(
    "motivo, mensagem",
    [
        ("", "Informe o motivo"),
        ("  ", "Informe o motivo"),
        (None, "Informe o motivo"),
        ("ok", "Explique o motivo com pelo menos 3 letras"),
        ("x" * 256, "Use no máximo 255 caracteres no motivo"),
    ],
)
def test_cancelar_pagamento_exige_motivo(api, paga, motivo, mensagem):
    assert erros_de(cancelar_pagamento(api, paga["id"], motivo))["motivo"] == mensagem


def test_cancelar_pagamento_de_mensalidade_que_nao_existe(api):
    assert cancelar_pagamento(api, 2147483647).status_code == 404
    assert cancelar_pagamento(api, 2147483648).status_code == 422


# ======================= Pagamento da empresa padrinha =======================


@pytest.fixture
def cobranca_paga(api, novo_aluno) -> dict:
    """A empresa apadrinha 2 alunos de R$ 150,00; a nota de novembro foi emitida e paga."""
    padrinho = cobrancas.novo_padrinho(api)
    for nome in ("Ana Lima", "Bruno Dias"):
        cobrancas.apadrinhar(api, novo_aluno(nome), padrinho)
    cobrancas.gerar(api)
    [cobranca] = cobrancas.cobrancas(api)
    assert cobrancas.emitir(api, cobranca["id"], numero="NF-1").status_code == 200
    resposta = cobrancas.pagar(api, cobranca["id"], valor_pago="300.00")
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def cancelar_pagamento_da_empresa(cliente, cobranca_id, motivo=MOTIVO):
    return cliente.patch(
        f"/api/cobrancas/{cobranca_id}/pagamento/cancelar", json={"motivo": motivo}
    )


def test_cancelar_pagamento_da_empresa_volta_a_cobranca_para_emitida(api, cobranca_paga):
    resposta = cancelar_pagamento_da_empresa(api, cobranca_paga["id"])

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert (dados["status"], dados["situacao"]) == ("emitida", "a_vencer")
    assert dados["pagamento"] is None
    assert dados["nota"]["numero_nota"] == "NF-1"  # a nota emitida continua valendo
    [cancelado] = dados["pagamentos_cancelados"]
    assert (cancelado["valor_pago"], cancelado["cancelamento"]["motivo"]) == ("300.00", MOTIVO)


def status_das_mensalidades(db) -> set[str]:
    db.expire_all()
    return {m.status.value for m in db.scalars(select(Mensalidade))}


def test_as_mensalidades_dos_alunos_deixam_de_estar_quitadas(api, db, cobranca_paga):
    assert status_das_mensalidades(db) == {"paga"}
    cancelar_pagamento_da_empresa(api, cobranca_paga["id"])
    assert status_das_mensalidades(db) == {"pendente"}


def test_depois_de_cancelar_a_empresa_pode_pagar_de_novo(api, db, cobranca_paga):
    cancelar_pagamento_da_empresa(api, cobranca_paga["id"])
    resposta = api.post(
        f"/api/cobrancas/{cobranca_paga['id']}/pagamento",
        json={"data_pagamento": "2026-11-05", "valor_pago": "300.00", "forma_pagamento": "boleto"},
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["status"] == "paga"
    assert len(resposta.json()["pagamentos_cancelados"]) == 1
    assert status_das_mensalidades(db) == {"paga"}


def test_cobranca_sem_pagamento_nao_tem_o_que_cancelar(api, cobranca_paga):
    cancelar_pagamento_da_empresa(api, cobranca_paga["id"])
    resposta = cancelar_pagamento_da_empresa(api, cobranca_paga["id"])
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Esta cobrança não tem pagamento para cancelar"


def test_mensalidade_apadrinhada_nao_cancela_pagamento_pela_mensalidade(api, db, cobranca_paga):
    mensalidade = db.scalars(select(Mensalidade)).first()
    resposta = cancelar_pagamento(api, mensalidade.id)
    assert resposta.status_code == 409
    assert "cobrança da empresa" in resposta.json()["detail"]


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.CONSULTA])
def test_so_o_administrador_cancela_pagamento_da_empresa(api_como, cobranca_paga, perfil):
    resposta = cancelar_pagamento_da_empresa(api_como(perfil), cobranca_paga["id"])
    assert resposta.status_code == 403


def test_cancelar_pagamento_da_empresa_exige_motivo(api, cobranca_paga):
    resposta = cancelar_pagamento_da_empresa(api, cobranca_paga["id"], "")
    assert erros_de(resposta)["motivo"] == "Informe o motivo"


# ======================= Despesas e receitas =======================

TIPOS = {
    "despesas": {
        "modelo": Despesa,
        "categorias": "/api/categorias-despesa",
        "corpo": {
            "data_despesa": "2026-11-03",
            "valor": "89.90",
            "descricao": "Placa controladora",
            "favorecido": "Loja Robótica Ltda",
        },
        "data": "data_despesa",
        "nome": "despesa",
    },
    "receitas": {
        "modelo": Receita,
        "categorias": "/api/categorias-receita",
        "corpo": {
            "data_receita": "2026-11-03",
            "valor": "500.00",
            "origem": "Mineração Vale Verde",
            "descricao": "Patrocínio da feira",
        },
        "data": "data_receita",
        "nome": "receita",
    },
}


@pytest.fixture(params=list(TIPOS))
def tipo(request) -> str:
    return request.param


def categoria_de(api, tipo, posicao=0) -> int:
    return api.get(TIPOS[tipo]["categorias"]).json()[posicao]["id"]


def lancar(api, tipo, **campos) -> dict:
    corpo = TIPOS[tipo]["corpo"] | {"categoria_id": categoria_de(api, tipo)} | campos
    resposta = api.post(f"/api/{tipo}", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def cancelar(cliente, tipo, lancamento_id, motivo=MOTIVO):
    return cliente.patch(f"/api/{tipo}/{lancamento_id}/cancelar", json={"motivo": motivo})


def corrigir(cliente, api, tipo, lancamento_id, motivo=MOTIVO, **campos):
    corpo = (
        TIPOS[tipo]["corpo"]
        | {"categoria_id": categoria_de(api, tipo), "valor": "98.90", "motivo": motivo}
        | campos
    )
    return cliente.post(f"/api/{tipo}/{lancamento_id}/corrigir", json=corpo)


def test_cancelar_marca_o_lancamento_e_ele_continua_na_lista(api, tipo):
    lancamento = lancar(api, tipo)
    resposta = cancelar(api, tipo, lancamento["id"])

    assert resposta.status_code == 200, resposta.text
    cancelamento = resposta.json()["cancelamento"]
    assert cancelamento["motivo"] == MOTIVO
    assert cancelamento["cancelado_por"].startswith("Usuário administrador")
    [na_lista] = api.get(f"/api/{tipo}", params={"mes": "2026-11"}).json()
    assert na_lista["id"] == lancamento["id"]
    assert na_lista["cancelamento"]["motivo"] == MOTIVO


def test_lancamento_ativo_nao_tem_cancelamento(api, tipo):
    lancamento = lancar(api, tipo)
    assert (lancamento["cancelamento"], lancamento["substitui_id"]) == (None, None)


def test_nao_cancela_duas_vezes(api, tipo):
    lancamento = lancar(api, tipo)
    cancelar(api, tipo, lancamento["id"])
    resposta = cancelar(api, tipo, lancamento["id"])
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == f"Esta {TIPOS[tipo]['nome']} já está cancelada"


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.CONSULTA])
def test_so_o_administrador_cancela_lancamento(api, api_como, tipo, perfil):
    lancamento = lancar(api, tipo)
    assert cancelar(api_como(perfil), tipo, lancamento["id"]).status_code == 403


def test_cancelar_lancamento_exige_motivo(api, tipo):
    lancamento = lancar(api, tipo)
    assert erros_de(cancelar(api, tipo, lancamento["id"], " "))["motivo"] == "Informe o motivo"


def test_cancelar_lancamento_que_nao_existe(api, tipo):
    resposta = cancelar(api, tipo, 2147483647)
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == f"{TIPOS[tipo]['nome'].capitalize()} não encontrada"


def test_corrigir_cancela_o_errado_e_registra_o_certo_apontando_para_ele(api, tipo):
    errado = lancar(api, tipo)
    resposta = corrigir(api, api, tipo, errado["id"], valor="98.90")

    assert resposta.status_code == 201, resposta.text
    certo = resposta.json()
    assert certo["id"] != errado["id"]
    assert (certo["valor"], certo["substitui_id"], certo["cancelamento"]) == (
        "98.90",
        errado["id"],
        None,
    )
    por_id = {
        lancamento["id"]: lancamento
        for lancamento in api.get(f"/api/{tipo}", params={"mes": "2026-11"}).json()
    }
    assert por_id[errado["id"]]["cancelamento"]["motivo"] == MOTIVO
    assert por_id[errado["id"]]["substituida_por_id"] == certo["id"]


def test_lancamento_ja_corrigido_nao_e_corrigido_de_novo(api, tipo):
    errado = lancar(api, tipo)
    corrigir(api, api, tipo, errado["id"])
    resposta = corrigir(api, api, tipo, errado["id"])
    assert resposta.status_code == 409


def test_correcao_invalida_nao_cancela_nada(api, db, tipo):
    errado = lancar(api, tipo)
    resposta = corrigir(api, api, tipo, errado["id"], valor="0")
    assert resposta.status_code == 422
    db.expire_all()
    modelo = TIPOS[tipo]["modelo"]
    assert db.get(modelo, errado["id"]).cancelado_em is None
    assert len(db.scalars(select(modelo)).all()) == 1


def test_correcao_com_categoria_inativa_nao_cancela_nada(api, db, tipo):
    errado = lancar(api, tipo)
    inativa = api.post(TIPOS[tipo]["categorias"], json={"nome": "Antiga", "ativo": False}).json()
    resposta = corrigir(api, api, tipo, errado["id"], categoria_id=inativa["id"])
    assert resposta.status_code == 422
    db.expire_all()
    assert db.get(TIPOS[tipo]["modelo"], errado["id"]).cancelado_em is None


def test_correcao_exige_motivo_em_portugues(api, tipo):
    errado = lancar(api, tipo)
    corpo = TIPOS[tipo]["corpo"] | {"categoria_id": categoria_de(api, tipo)}
    resposta = api.post(f"/api/{tipo}/{errado['id']}/corrigir", json=corpo)
    assert erros_de(resposta)["motivo"] == "Informe o motivo"


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.CONSULTA])
def test_so_o_administrador_corrige(api, api_como, tipo, perfil):
    errado = lancar(api, tipo)
    assert corrigir(api_como(perfil), api, tipo, errado["id"]).status_code == 403


def test_nao_existe_rota_para_apagar_lancamento(api, tipo):
    lancamento = lancar(api, tipo)
    assert api.delete(f"/api/{tipo}/{lancamento['id']}").status_code in (404, 405)


# ======================= O banco garante o cancelamento completo =======================


def test_banco_recusa_pagamento_cancelado_sem_motivo(db, paga):
    with pytest.raises(IntegrityError, match="cancelamento_completo"):
        db.execute(text("UPDATE pagamentos SET cancelado_em = now()"))


def test_banco_recusa_pagamento_da_empresa_cancelado_sem_autor(db, cobranca_paga):
    with pytest.raises(IntegrityError, match="cancelamento_completo"):
        db.execute(
            text("UPDATE pagamentos_cobranca SET cancelado_em = now(), motivo_cancelamento = 'x'")
        )


def test_banco_recusa_despesa_cancelada_sem_motivo(api, db):
    lancamento = lancar(api, "despesas")
    with pytest.raises(IntegrityError, match="cancelamento_completo"):
        db.execute(
            text("UPDATE despesas SET cancelado_em = now() WHERE id = :id"),
            {"id": lancamento["id"]},
        )


def test_banco_recusa_duas_correcoes_do_mesmo_lancamento(api, db):
    errado = lancar(api, "receitas")
    corrigir(api, api, "receitas", errado["id"])
    with pytest.raises(IntegrityError, match="uq_receitas_substitui_id"):
        db.execute(
            text(
                "INSERT INTO receitas (data_receita, valor, categoria_id, origem, criado_por_id,"
                " substitui_id) SELECT data_receita, valor, categoria_id, origem, criado_por_id,"
                " :id FROM receitas WHERE id = :id"
            ),
            {"id": errado["id"]},
        )
