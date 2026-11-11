from datetime import date

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.core import tempo
from app.db.session import engine
from app.models import Perfil
from app.routers import cobrancas as rota_de_cobrancas
from app.routers import mensalidades as rota_de_mensalidades

HOJE = date(2026, 11, 5)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Todos os testes rodam "em 5 de novembro de 2026", para não dependerem do dia em que rodam."""
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)


# ---------- Montagem do cenário ----------


def novo_padrinho(cliente, nome="Sartori Serviços", **campos) -> dict:
    corpo = {
        "nome": nome,
        "telefone": "(31) 98888-7777",
        "email": "financeiro@sartori.com.br",
        "dia_vencimento": 25,
    } | campos
    resposta = cliente.post("/api/padrinhos", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def apadrinhar(cliente, aluno, padrinho, **campos) -> dict:
    corpo = {
        "aluno_id": aluno["id"],
        "data_inicio": "2026-01-15",
        "valor_mensalidade": "150.00",
        "bolsa": "apadrinhada",
        "padrinho_id": padrinho["id"],
    } | campos
    resposta = cliente.post("/api/matriculas", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def gerar(cliente, mes="2026-11") -> dict:
    resposta = cliente.post("/api/mensalidades/gerar", json={"competencia": mes})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def cobrancas(cliente, **filtros) -> list[dict]:
    resposta = cliente.get("/api/cobrancas", params=filtros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def nota(numero="NF-100", emissao="2026-11-03", vencimento="2026-11-25") -> dict:
    return {"numero_nota": numero, "data_emissao": emissao, "data_vencimento": vencimento}


def emitir(cliente, cobranca_id, **campos):
    return cliente.patch(f"/api/cobrancas/{cobranca_id}/nota", json=nota(**campos))


def pagamento(**campos) -> dict:
    return {
        "data_pagamento": "2026-11-04",
        "valor_pago": "450.00",
        "forma_pagamento": "pix",
    } | campos


def pagar(cliente, cobranca_id, **campos):
    return cliente.post(f"/api/cobrancas/{cobranca_id}/pagamento", json=pagamento(**campos))


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


@pytest.fixture
def tres_alunos(api, novo_aluno):
    """A empresa Sartori apadrinha 3 alunos de R$ 150,00 e o mês de novembro está gerado."""
    padrinho = novo_padrinho(api, emitir_ate_dia=10)
    for nome in ("Ana Lima", "Bruno Dias", "Carla Reis"):
        apadrinhar(api, novo_aluno(nome), padrinho)
    gerar(api)
    return padrinho


@pytest.fixture
def cobranca(api, tres_alunos) -> dict:
    return cobrancas(api)[0]


@pytest.fixture
def emitida(api, cobranca) -> dict:
    resposta = emitir(api, cobranca["id"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@pytest.fixture
def paga(api, emitida) -> dict:
    resposta = pagar(api, emitida["id"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# ---------- Geração: uma cobrança por empresa, com a soma dos alunos (RN18) ----------


def test_gerar_cria_uma_cobranca_com_a_soma_dos_alunos(api, tres_alunos):
    lista = cobrancas(api)

    assert len(lista) == 1
    c = lista[0]
    assert c["padrinho"] == {"id": tres_alunos["id"], "nome": "Sartori Serviços", "ativo": True}
    assert (c["competencia"], c["valor"]) == ("2026-11-01", "450.00")
    assert (c["status"], c["situacao"]) == ("a_emitir", "a_emitir")
    assert [a["aluno"]["nome"] for a in c["alunos"]] == ["Ana Lima", "Bruno Dias", "Carla Reis"]
    assert {a["valor"] for a in c["alunos"]} == {"150.00"}
    assert c["nota"] is None and c["pagamento"] is None and c["motivo"] is None
    assert c["gerada_por"].startswith("Usuário administrador")


def test_o_resultado_da_geracao_conta_os_alunos_incluidos_e_as_cobrancas_novas(api, novo_aluno):
    padrinho = novo_padrinho(api)
    outra = novo_padrinho(api, "Beta Engenharia")
    apadrinhar(api, novo_aluno(), padrinho)
    apadrinhar(api, novo_aluno(), padrinho)
    apadrinhar(api, novo_aluno(), outra)

    resultado = gerar(api)

    assert resultado["apadrinhados"] == 3
    assert resultado["apadrinhados_incluidos"] == 3
    assert resultado["cobrancas_criadas"] == 2
    assert resultado["geradas"] == 0  # nenhuma mensalidade foi cobrada de responsável


def test_o_vencimento_e_sugerido_pelo_dia_combinado_e_o_prazo_pela_empresa(api, novo_aluno):
    com_prazo = novo_padrinho(api, "Com prazo", dia_vencimento=25, emitir_ate_dia=10)
    sem_prazo = novo_padrinho(api, "Sem prazo", dia_vencimento=5)
    apadrinhar(api, novo_aluno(), com_prazo)
    apadrinhar(api, novo_aluno(), sem_prazo)
    gerar(api)

    por_nome = {c["padrinho"]["nome"]: c for c in cobrancas(api)}

    assert (por_nome["Com prazo"]["data_vencimento"], por_nome["Com prazo"]["limite_emissao"]) == (
        "2026-11-25",
        "2026-11-10",
    )
    assert (por_nome["Sem prazo"]["data_vencimento"], por_nome["Sem prazo"]["limite_emissao"]) == (
        "2026-11-05",
        None,
    )


def test_cada_empresa_tem_a_propria_cobranca(api, novo_aluno):
    a, b = novo_padrinho(api, "Alfa"), novo_padrinho(api, "Beta")
    apadrinhar(api, novo_aluno(), a)
    apadrinhar(api, novo_aluno(), a, valor_mensalidade="80.50")
    apadrinhar(api, novo_aluno(), b)
    gerar(api)

    valores = {c["padrinho"]["nome"]: (c["valor"], len(c["alunos"])) for c in cobrancas(api)}

    assert valores == {"Alfa": ("230.50", 2), "Beta": ("150.00", 1)}


def test_gerar_de_novo_nao_duplica_a_cobranca(api, tres_alunos):
    antes = cobrancas(api)
    segundo = gerar(api)

    assert cobrancas(api) == antes
    assert (segundo["apadrinhados_incluidos"], segundo["cobrancas_criadas"]) == (0, 0)


def test_aluno_que_entra_depois_vai_para_a_cobranca_ainda_a_emitir(api, tres_alunos, novo_aluno):
    antes = cobrancas(api)[0]
    apadrinhar(api, novo_aluno("Davi Costa"), tres_alunos, valor_mensalidade="100.00")

    resultado = gerar(api)

    depois = cobrancas(api)
    assert len(depois) == 1
    assert depois[0]["id"] == antes["id"]
    assert depois[0]["valor"] == "550.00"
    assert [a["aluno"]["nome"] for a in depois[0]["alunos"]][-1] == "Davi Costa"
    assert (resultado["apadrinhados_incluidos"], resultado["cobrancas_criadas"]) == (1, 0)


def test_aluno_que_entra_depois_da_nota_forma_uma_cobranca_complementar(
    api, emitida, tres_alunos, novo_aluno
):
    apadrinhar(api, novo_aluno("Davi Costa"), tres_alunos, valor_mensalidade="100.00")

    resultado = gerar(api)

    lista = cobrancas(api)
    assert len(lista) == 2
    complementar = next(c for c in lista if c["status"] == "a_emitir")
    original = next(c for c in lista if c["id"] == emitida["id"])
    assert (complementar["valor"], len(complementar["alunos"])) == ("100.00", 1)
    # A cobrança já emitida não muda: o valor da nota que a empresa recebeu continua o mesmo
    assert (original["valor"], len(original["alunos"]), original["status"]) == (
        "450.00",
        3,
        "emitida",
    )
    assert (resultado["apadrinhados_incluidos"], resultado["cobrancas_criadas"]) == (1, 1)


def test_aluno_que_ja_foi_cobrado_do_responsavel_no_mes_nao_entra_na_cobranca(api, novo_aluno):
    """Quem pagou pelo responsável e virou apadrinhado no mesmo mês não é cobrado em dobro."""
    aluno = novo_aluno("Pedro")
    padrinho = novo_padrinho(api)
    antiga = api.post(
        "/api/matriculas",
        json={"aluno_id": aluno["id"], "data_inicio": "2026-01-15", "valor_mensalidade": "150.00"},
    ).json()
    assert gerar(api, "2026-10")["geradas"] == 1
    api.patch(f"/api/matriculas/{antiga['id']}/encerrar", json={"data_encerramento": "2026-10-14"})
    apadrinhar(api, aluno, padrinho, data_inicio="2026-10-15")

    resultado = gerar(api, "2026-10")

    assert resultado["apadrinhados"] == 1
    assert resultado["apadrinhados_incluidos"] == 0
    assert cobrancas(api) == []
    assert len(api.get("/api/mensalidades").json()) == 1


def test_matricula_encerrada_antes_do_mes_nao_entra_e_a_encerrada_no_mes_entra(api, novo_aluno):
    padrinho = novo_padrinho(api)
    saiu_em_setembro = apadrinhar(api, novo_aluno("Saiu em setembro"), padrinho)
    saiu_em_outubro = apadrinhar(api, novo_aluno("Saiu em outubro"), padrinho)
    api.patch(
        f"/api/matriculas/{saiu_em_setembro['id']}/encerrar",
        json={"data_encerramento": "2026-09-20"},
    )
    api.patch(
        f"/api/matriculas/{saiu_em_outubro['id']}/encerrar",
        json={"data_encerramento": "2026-10-20"},
    )

    gerar(api, "2026-10")

    nomes = [a["aluno"]["nome"] for a in cobrancas(api)[0]["alunos"]]
    assert nomes == ["Saiu em outubro"]


def test_empresa_inativa_continua_sendo_cobrada(api, novo_aluno):
    padrinho = novo_padrinho(api)
    apadrinhar(api, novo_aluno(), padrinho)
    api.put(
        f"/api/padrinhos/{padrinho['id']}",
        json={
            "nome": padrinho["nome"],
            "telefone": padrinho["telefone"],
            "email": padrinho["email"],
            "dia_vencimento": 25,
            "ativo": False,
        },
    )

    gerar(api)

    assert cobrancas(api)[0]["padrinho"]["ativo"] is False


def test_da_para_gerar_um_mes_passado(api, novo_aluno):
    apadrinhar(api, novo_aluno(), novo_padrinho(api))

    gerar(api, "2026-09")

    assert [c["competencia"] for c in cobrancas(api)] == ["2026-09-01"]
    assert cobrancas(api)[0]["data_vencimento"] == "2026-09-25"


def test_geracao_que_perde_a_corrida_nao_deixa_cobranca_vazia(api, emitida, monkeypatch):
    """Outra geração incluiu os mesmos alunos um instante antes: esta não cria cobrança vazia."""
    monkeypatch.setattr(rota_de_mensalidades, "alunos_ja_cobrados", lambda *_: set())

    resultado = gerar(api)

    assert (resultado["apadrinhados_incluidos"], resultado["cobrancas_criadas"]) == (0, 0)
    assert [c["id"] for c in cobrancas(api)] == [emitida["id"]]


# ---------- As mensalidades de apadrinhados saem da conta do responsável (RN16) ----------


def test_mensalidades_de_apadrinhados_nao_aparecem_na_lista_dos_responsaveis(api, tres_alunos):
    assert api.get("/api/mensalidades", params={"mes": "2026-11"}).json() == []


def test_mensalidades_de_apadrinhados_nao_entram_nas_pendencias(api, tres_alunos, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 3, 1))  # muito depois do vencimento

    pendencias = api.get("/api/pendencias").json()

    assert pendencias["grupos"] == []
    assert pendencias["resumo"]["total_em_aberto"] == "0.00"


@pytest.mark.parametrize(
    "metodo, caminho, corpo",
    [
        (
            "post",
            "pagamento",
            {"data_pagamento": "2026-11-04", "valor_pago": "150", "forma_pagamento": "pix"},
        ),
        ("patch", "isentar", {"motivo": "Recesso"}),
        ("patch", "cancelar", {"motivo": "Gerada por engano"}),
    ],
)
def test_mensalidade_de_apadrinhado_nao_e_paga_nem_alterada_a_parte(
    api, cobranca, db, metodo, caminho, corpo
):
    mensalidade_id = cobranca["alunos"][0]["mensalidade_id"]

    resposta = getattr(api, metodo)(f"/api/mensalidades/{mensalidade_id}/{caminho}", json=corpo)

    assert resposta.status_code == 409
    assert "faz parte da cobrança da empresa" in resposta.json()["detail"]
    assert cobrancas(api)[0]["status"] == "a_emitir"


# ---------- Registrar a nota (RF31) ----------


def test_registrar_a_nota_emite_a_cobranca(api, cobranca, db):
    resposta = emitir(api, cobranca["id"], numero="NF-2026/100", vencimento="2026-11-28")

    assert resposta.status_code == 200, resposta.text
    c = resposta.json()
    assert (c["status"], c["situacao"]) == ("emitida", "a_vencer")
    assert (c["data_vencimento"], c["valor"]) == ("2026-11-28", "450.00")
    assert c["nota"]["numero_nota"] == "NF-2026/100"
    assert c["nota"]["data_emissao"] == "2026-11-03"
    assert c["nota"]["registrada_por"].startswith("Usuário administrador")
    assert c["nota"]["registrada_em"]
    vencimentos = db.execute(
        text("SELECT DISTINCT data_vencimento FROM mensalidades WHERE cobranca_id = :id"),
        {"id": cobranca["id"]},
    ).all()
    assert [v[0] for v in vencimentos] == [date(2026, 11, 28)]


def test_limites_aceitos_da_nota(api, cobranca):
    """30 caracteres no número e vencimento exatamente 366 dias depois da emissão valem."""
    resposta = emitir(api, cobranca["id"], numero="N" * 30, vencimento="2027-11-04")

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["nota"]["numero_nota"] == "N" * 30


def test_as_mensalidades_nascem_com_o_vencimento_combinado_com_a_empresa(api, cobranca, db):
    vencimentos = db.execute(
        text("SELECT DISTINCT data_vencimento FROM mensalidades WHERE cobranca_id = :id"),
        {"id": cobranca["id"]},
    ).all()

    assert [v[0] for v in vencimentos] == [date(2026, 11, 25)]


def test_o_numero_da_nota_e_aparado_e_os_espacos_repetidos_viram_um(api, cobranca):
    resposta = emitir(api, cobranca["id"], numero="  NF   2026   100  ")

    assert resposta.json()["nota"]["numero_nota"] == "NF 2026 100"


def test_a_nota_pode_ser_emitida_no_dia_do_vencimento_e_com_vencimento_no_mesmo_dia(api, cobranca):
    resposta = emitir(api, cobranca["id"], emissao="2026-11-05", vencimento="2026-11-05")

    assert resposta.status_code == 200, resposta.text


def test_a_nota_pode_ser_corrigida_enquanto_nao_foi_paga(api, emitida):
    resposta = emitir(api, emitida["id"], numero="NF-101", vencimento="2026-11-30")

    assert resposta.status_code == 200
    c = resposta.json()
    assert (c["status"], c["nota"]["numero_nota"], c["data_vencimento"]) == (
        "emitida",
        "NF-101",
        "2026-11-30",
    )


def test_registrar_o_mesmo_numero_na_mesma_cobranca_nao_e_repeticao(api, emitida):
    assert emitir(api, emitida["id"], numero="NF-100").status_code == 200


def test_cobranca_paga_nao_tem_a_nota_alterada(api, paga):
    resposta = emitir(api, paga["id"], numero="NF-999")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Uma cobrança paga não pode ter a nota alterada"
    assert cobrancas(api)[0]["nota"]["numero_nota"] == "NF-100"


def test_cobranca_cancelada_nao_recebe_nota(api, cobranca):
    api.patch(f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": "Empresa saiu"})

    resposta = emitir(api, cobranca["id"])

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Uma cobrança cancelada não recebe nota"


def test_o_numero_da_nota_nao_repete_em_outra_cobranca(api, emitida, novo_aluno):
    outra = novo_padrinho(api, "Beta Engenharia")
    apadrinhar(api, novo_aluno(), outra)
    gerar(api)
    segunda = next(c for c in cobrancas(api) if c["padrinho"]["nome"] == "Beta Engenharia")

    for numero in ("NF-100", "nf-100", " Nf-100 "):
        resposta = emitir(api, segunda["id"], numero=numero)
        assert resposta.status_code == 409, numero
        assert resposta.json()["detail"] == "Já existe uma cobrança com esse número de nota"
    assert emitir(api, segunda["id"], numero="NF-101").status_code == 200


def test_numero_repetido_no_mesmo_instante_tambem_vira_409(api, emitida, novo_aluno, monkeypatch):
    """Outro pedido registrou o número entre a conferência e a gravação: o banco recusa."""
    outra = novo_padrinho(api, "Beta Engenharia")
    apadrinhar(api, novo_aluno(), outra)
    gerar(api)
    segunda = next(c for c in cobrancas(api) if c["padrinho"]["nome"] == "Beta Engenharia")
    monkeypatch.setattr(rota_de_cobrancas, "numero_ja_usado", lambda *_: False)

    resposta = emitir(api, segunda["id"], numero="NF-100")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe uma cobrança com esse número de nota"
    assert [c["status"] for c in cobrancas(api) if c["id"] == segunda["id"]] == ["a_emitir"]


@pytest.mark.parametrize(
    "campos, campo, mensagem",
    [
        ({"numero": ""}, "numero_nota", "Informe o número da nota"),
        ({"numero": "   "}, "numero_nota", "Informe o número da nota"),
        ({"numero": "N" * 31}, "numero_nota", "Use no máximo 30 caracteres no número da nota"),
        ({"emissao": ""}, "data_emissao", "Informe a data de emissão da nota"),
        ({"emissao": "2026-11-06"}, "data_emissao", "A data de emissão não pode ser no futuro"),
        ({"emissao": "1999-12-31"}, "data_emissao", "Essa data é antiga demais"),
        ({"vencimento": ""}, "data_vencimento", "Informe o vencimento da cobrança"),
        (
            {"vencimento": "2026-11-02"},
            "data_vencimento",
            "O vencimento não pode ser antes da emissão da nota",
        ),
        (
            {"vencimento": "2027-11-05"},
            "data_vencimento",
            "O vencimento deve ser em até um ano depois da emissão",
        ),
        ({"vencimento": "1999-12-31"}, "data_vencimento", "Essa data é antiga demais"),
    ],
)
def test_nota_com_dados_invalidos_e_recusada(api, cobranca, campos, campo, mensagem):
    resposta = emitir(api, cobranca["id"], **campos)

    assert erros_de(resposta)[campo].startswith(mensagem[:25])
    assert cobrancas(api)[0]["status"] == "a_emitir"


def test_vencimento_antes_do_mes_da_cobranca_e_recusado(api, cobranca):
    resposta = emitir(api, cobranca["id"], emissao="2026-10-20", vencimento="2026-10-31")

    assert erros_de(resposta) == {
        "data_vencimento": "O vencimento não pode ser antes do mês da cobrança"
    }


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"numero_nota": "NF-1"},
        {"numero_nota": None, "data_emissao": None, "data_vencimento": None},
        {"numero_nota": 12, "data_emissao": "2026-11-03", "data_vencimento": "2026-11-25"},
        {"numero_nota": "NF-1", "data_emissao": "ontem", "data_vencimento": "2026-11-25"},
        {"numero_nota": "NF-1", "data_emissao": "2026-02-30", "data_vencimento": "2026-11-25"},
        {"numero_nota": "NF\x00", "data_emissao": "2026-11-03", "data_vencimento": "2026-11-25"},
    ],
)
def test_nota_malformada_da_422_e_nunca_500(api, cobranca, corpo):
    resposta = api.patch(f"/api/cobrancas/{cobranca['id']}/nota", json=corpo)

    assert resposta.status_code == 422, resposta.text


def test_campos_extras_na_nota_sao_ignorados(api, cobranca):
    corpo = nota() | {"status": "paga", "valor": "1.00", "id": 99, "padrinho_id": 7}

    resposta = api.patch(f"/api/cobrancas/{cobranca['id']}/nota", json=corpo)

    assert resposta.status_code == 200
    c = resposta.json()
    assert (c["status"], c["valor"], c["id"]) == ("emitida", "450.00", cobranca["id"])


# ---------- A situação é calculada (RN07) ----------


@pytest.mark.parametrize(
    "hoje, situacao, dias",
    [
        (date(2026, 11, 24), "a_vencer", 0),
        (date(2026, 11, 25), "a_vencer", 0),  # no dia do vencimento ainda não está atrasada
        (date(2026, 11, 26), "atrasada", 1),
        (date(2026, 12, 25), "atrasada", 30),
    ],
)
def test_emitida_so_fica_atrasada_a_partir_do_dia_seguinte_ao_vencimento(
    api, emitida, monkeypatch, hoje, situacao, dias
):
    monkeypatch.setattr(tempo, "hoje", lambda: hoje)

    c = cobrancas(api)[0]

    assert (c["situacao"], c["dias_em_atraso"]) == (situacao, dias)


def test_a_emitir_nunca_fica_atrasada(api, cobranca, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 6, 1))

    c = cobrancas(api)[0]

    assert (c["situacao"], c["dias_em_atraso"]) == ("a_emitir", 0)


@pytest.mark.parametrize(
    "hoje, atrasada",
    [(date(2026, 11, 9), False), (date(2026, 11, 10), False), (date(2026, 11, 11), True)],
)
def test_emissao_atrasada_so_depois_do_prazo_da_empresa(api, cobranca, monkeypatch, hoje, atrasada):
    monkeypatch.setattr(tempo, "hoje", lambda: hoje)

    c = cobrancas(api)[0]

    assert c["limite_emissao"] == "2026-11-10"
    assert c["emissao_atrasada"] is atrasada
    assert c["situacao"] == "a_emitir"


@pytest.mark.parametrize("hoje, quantas", [(date(2026, 11, 10), 0), (date(2026, 11, 11), 1)])
def test_filtro_de_emissao_atrasada_so_depois_do_prazo(api, cobranca, monkeypatch, hoje, quantas):
    monkeypatch.setattr(tempo, "hoje", lambda: hoje)

    assert len(cobrancas(api, situacao="emissao_atrasada")) == quantas
    assert len(cobrancas(api, situacao="a_emitir")) == 1


def test_empresa_sem_prazo_nunca_tem_emissao_atrasada(api, novo_aluno, monkeypatch):
    apadrinhar(api, novo_aluno(), novo_padrinho(api))
    gerar(api)
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 1, 1))

    assert cobrancas(api)[0]["emissao_atrasada"] is False


def test_depois_da_nota_a_emissao_deixa_de_estar_atrasada(api, cobranca, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 20))
    assert cobrancas(api)[0]["emissao_atrasada"] is True

    emitir(api, cobranca["id"], emissao="2026-11-20", vencimento="2026-11-30")

    assert cobrancas(api)[0]["emissao_atrasada"] is False


# ---------- Registrar o pagamento (RF31) ----------


def test_pagamento_quita_a_cobranca_e_as_mensalidades(api, emitida, db):
    resposta = pagar(api, emitida["id"], observacao=" PIX da matriz ")

    assert resposta.status_code == 201, resposta.text
    c = resposta.json()
    assert (c["status"], c["situacao"]) == ("paga", "paga")
    assert c["pagamento"]["data_pagamento"] == "2026-11-04"
    assert (c["pagamento"]["valor_pago"], c["pagamento"]["forma_pagamento"]) == ("450.00", "pix")
    assert c["pagamento"]["observacao"] == "PIX da matriz"
    assert c["pagamento"]["registrado_por"].startswith("Usuário administrador")
    assert c["pagamento"]["registrado_em"]
    estados = db.execute(
        text("SELECT DISTINCT status FROM mensalidades WHERE cobranca_id = :id"),
        {"id": emitida["id"]},
    ).all()
    assert [e[0] for e in estados] == ["paga"]


@pytest.mark.parametrize("forma", ["pix", "transferencia", "boleto", "outra"])
def test_formas_de_pagamento_aceitas(api, emitida, forma):
    assert pagar(api, emitida["id"], forma_pagamento=forma).status_code == 201


@pytest.mark.parametrize("forma", ["dinheiro", "PIX", "", None, 1, "cartao"])
def test_forma_de_pagamento_desconhecida_e_recusada(api, emitida, forma):
    resposta = pagar(api, emitida["id"], forma_pagamento=forma)

    assert "forma_pagamento" in erros_de(resposta)
    assert cobrancas(api)[0]["status"] == "emitida"


def test_valor_diferente_exige_observacao(api, emitida):
    resposta = pagar(api, emitida["id"], valor_pago="400.00")

    erros = erros_de(resposta)
    assert erros == {
        "observacao": "O valor é diferente do cobrado (R$ 450,00). Explique o motivo na observação"
    }
    assert cobrancas(api)[0]["status"] == "emitida"


def test_valor_diferente_com_observacao_e_aceito_e_guarda_o_que_entrou(api, emitida):
    resposta = pagar(api, emitida["id"], valor_pago="400,00", observacao="Desconto combinado")

    assert resposta.status_code == 201, resposta.text
    c = resposta.json()
    assert (c["valor"], c["pagamento"]["valor_pago"]) == ("450.00", "400.00")


@pytest.mark.parametrize(
    "valor", ["0", "-1", "", "abc", "NaN", "Infinity", "-Infinity", "1.234", "100000000", None]
)
def test_valor_invalido_e_recusado(api, emitida, valor):
    resposta = pagar(api, emitida["id"], valor_pago=valor, observacao="x")

    assert "valor_pago" in erros_de(resposta)


@pytest.mark.parametrize(
    "data, trecho",
    [
        ("2026-11-06", "futuro"),
        ("1999-12-31", "antiga"),
        ("", "Informe"),
        ("2026-13-01", ""),
        (None, "Informe"),
    ],
)
def test_data_do_pagamento_invalida_e_recusada(api, emitida, data, trecho):
    resposta = pagar(api, emitida["id"], data_pagamento=data)

    assert trecho in erros_de(resposta)["data_pagamento"]


def test_pagamento_no_dia_de_hoje_e_aceito(api, emitida):
    assert pagar(api, emitida["id"], data_pagamento="2026-11-05").status_code == 201


def test_observacao_longa_demais_e_recusada(api, emitida):
    resposta = pagar(api, emitida["id"], observacao="x" * 256)

    assert "observacao" in erros_de(resposta)


def test_so_a_cobranca_emitida_recebe_pagamento(api, cobranca):
    resposta = pagar(api, cobranca["id"])

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Registre a nota da cobrança antes de registrar o pagamento"


def test_cobranca_paga_nao_recebe_outro_pagamento(api, paga, db):
    resposta = pagar(api, paga["id"])

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Esta cobrança já foi paga"
    total = db.scalar(text("SELECT count(*) FROM pagamentos_cobranca"))
    assert total == 1


def test_cobranca_cancelada_nao_recebe_pagamento(api, emitida):
    api.patch(f"/api/cobrancas/{emitida['id']}/cancelar", json={"motivo": "Nota errada"})

    resposta = pagar(api, emitida["id"])

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Uma cobrança cancelada não recebe pagamento"


def test_gerar_de_novo_depois_do_pagamento_nao_reabre_nada(api, paga):
    resultado = gerar(api)

    assert (resultado["apadrinhados_incluidos"], resultado["cobrancas_criadas"]) == (0, 0)
    assert [c["status"] for c in cobrancas(api)] == ["paga"]


# ---------- Cancelar (RN12, RN13) ----------


def test_administrador_cancela_a_cobranca_com_motivo(api, cobranca, db):
    resposta = api.patch(
        f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": "  Empresa   desistiu  "}
    )

    assert resposta.status_code == 200, resposta.text
    c = resposta.json()
    assert (c["status"], c["situacao"]) == ("cancelada", "cancelada")
    assert c["motivo"] == "Empresa desistiu"
    assert c["cancelada_por"].startswith("Usuário administrador")
    assert c["cancelada_em"]
    assert len(c["alunos"]) == 3  # nada é apagado: os alunos continuam na cobrança
    linhas = db.execute(
        text(
            "SELECT status, motivo_alteracao, alterado_por_id IS NOT NULL"
            " FROM mensalidades WHERE cobranca_id = :id"
        ),
        {"id": cobranca["id"]},
    ).all()
    assert set(linhas) == {("cancelada", "Empresa desistiu", True)}


def test_cancelar_uma_cobranca_emitida_tambem_funciona(api, emitida):
    resposta = api.patch(f"/api/cobrancas/{emitida['id']}/cancelar", json={"motivo": "Nota errada"})

    assert resposta.status_code == 200
    c = resposta.json()
    assert (c["status"], c["nota"]["numero_nota"]) == ("cancelada", "NF-100")


def test_cobranca_paga_nao_pode_ser_cancelada(api, paga):
    resposta = api.patch(f"/api/cobrancas/{paga['id']}/cancelar", json={"motivo": "Engano"})

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Uma cobrança paga não pode ser cancelada"
    assert cobrancas(api)[0]["status"] == "paga"


def test_cobranca_cancelada_nao_e_cancelada_de_novo_e_guarda_o_primeiro_motivo(api, cobranca):
    api.patch(f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": "Primeiro motivo"})

    resposta = api.patch(f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": "Outro"})

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Esta cobrança já está cancelada"
    assert cobrancas(api)[0]["motivo"] == "Primeiro motivo"


def test_gerar_de_novo_nao_recria_a_cobranca_cancelada(api, cobranca):
    api.patch(f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": "Empresa saiu"})

    resultado = gerar(api)

    assert (resultado["apadrinhados_incluidos"], resultado["cobrancas_criadas"]) == (0, 0)
    assert [c["status"] for c in cobrancas(api)] == ["cancelada"]


@pytest.mark.parametrize("motivo", ["", "   ", "ab", "x" * 256, None])
def test_cancelar_exige_um_motivo_valido(api, cobranca, motivo):
    resposta = api.patch(f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": motivo})

    assert "motivo" in erros_de(resposta)
    assert cobrancas(api)[0]["status"] == "a_emitir"


# ---------- Quem pode o quê (RN13) ----------


def test_consulta_so_le(api_como, cobranca, emitida):
    consulta = api_como(Perfil.CONSULTA)

    assert consulta.get("/api/cobrancas").status_code == 200
    assert consulta.get(f"/api/cobrancas/{cobranca['id']}").status_code == 200
    assert emitir(consulta, cobranca["id"]).status_code == 403
    assert pagar(consulta, cobranca["id"]).status_code == 403
    assert (
        consulta.patch(
            f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": "Teste"}
        ).status_code
        == 403
    )


def test_operador_registra_nota_e_pagamento_mas_nao_cancela(api, api_como, cobranca):
    operador = api_como(Perfil.OPERADOR)

    assert emitir(operador, cobranca["id"]).status_code == 200
    assert pagar(operador, cobranca["id"]).status_code == 201
    resposta = operador.patch(f"/api/cobrancas/{cobranca['id']}/cancelar", json={"motivo": "Teste"})
    assert resposta.status_code == 403
    assert cobrancas(api)[0]["status"] == "paga"


def test_sem_login_nada_funciona(sem_login, cobranca):
    assert sem_login.get("/api/cobrancas").status_code == 401
    assert sem_login.get(f"/api/cobrancas/{cobranca['id']}").status_code == 401
    assert emitir(sem_login, cobranca["id"]).status_code == 401
    assert pagar(sem_login, cobranca["id"]).status_code == 401
    assert sem_login.patch(f"/api/cobrancas/{cobranca['id']}/cancelar", json={}).status_code == 401


def test_o_perfil_e_conferido_antes_de_procurar_ou_validar(api_como):
    consulta, operador = api_como(Perfil.CONSULTA), api_como(Perfil.OPERADOR)

    assert emitir(consulta, 999999).status_code == 403
    assert consulta.patch("/api/cobrancas/999999/nota", json={}).status_code == 403
    assert operador.patch("/api/cobrancas/999999/cancelar", json={}).status_code == 403
    assert (
        operador.patch("/api/cobrancas/999999/cancelar", json={"motivo": "xx"}).status_code == 403
    )


@pytest.mark.parametrize("metodo", ["delete", "put", "post"])
def test_cobranca_nao_se_apaga_nem_se_edita_por_inteiro(api, cobranca, metodo):
    assert getattr(api, metodo)(f"/api/cobrancas/{cobranca['id']}").status_code == 405
    assert getattr(api, metodo)("/api/cobrancas").status_code in (405,)


def test_nao_ha_rota_para_consultar_o_pagamento_a_parte(api, cobranca):
    assert api.get(f"/api/cobrancas/{cobranca['id']}/pagamento").status_code == 405
    assert api.delete(f"/api/cobrancas/{cobranca['id']}/pagamento").status_code == 405


# ---------- Ids e a consulta de uma cobrança ----------


def test_consultar_uma_cobranca(api, cobranca):
    assert api.get(f"/api/cobrancas/{cobranca['id']}").json() == cobranca


def test_cobranca_que_nao_existe_da_404(api, api_como):
    operador = api_como(Perfil.OPERADOR)
    assert api.get("/api/cobrancas/999999").status_code == 404
    assert emitir(operador, 999999).status_code == 404
    assert pagar(operador, 999999).status_code == 404
    assert api.patch("/api/cobrancas/999999/cancelar", json={"motivo": "Teste"}).status_code == 404


@pytest.mark.parametrize("id_ruim", ["0", "-1", "2147483648", "99999999999999999999", "abc"])
def test_id_fora_do_limite_da_422(api, id_ruim):
    assert api.get(f"/api/cobrancas/{id_ruim}").status_code == 422
    assert api.patch(f"/api/cobrancas/{id_ruim}/nota", json=nota()).status_code == 422
    assert api.post(f"/api/cobrancas/{id_ruim}/pagamento", json=pagamento()).status_code == 422
    assert (
        api.patch(f"/api/cobrancas/{id_ruim}/cancelar", json={"motivo": "Teste"}).status_code == 422
    )


# ---------- A lista e os filtros ----------


def test_filtra_por_mes_e_por_empresa(api, novo_aluno):
    a, b = novo_padrinho(api, "Alfa"), novo_padrinho(api, "Beta")
    apadrinhar(api, novo_aluno(), a)
    apadrinhar(api, novo_aluno(), b)
    gerar(api, "2026-10")
    gerar(api, "2026-11")

    assert len(cobrancas(api)) == 4
    assert {c["competencia"] for c in cobrancas(api, mes="2026-11")} == {"2026-11-01"}
    assert len(cobrancas(api, mes="2026-10")) == 2
    assert [c["padrinho"]["nome"] for c in cobrancas(api, padrinho_id=a["id"])] == ["Alfa", "Alfa"]
    assert len(cobrancas(api, mes="2026-11", padrinho_id=b["id"])) == 1
    assert len(cobrancas(api, mes="")) == 4  # mês em branco quer dizer todos os meses
    assert cobrancas(api, mes="2025-01") == []


def test_a_lista_vem_do_mes_mais_recente_e_depois_pelo_nome_da_empresa(api, novo_aluno):
    for nome in ("Zeta", "Alfa"):
        apadrinhar(api, novo_aluno(), novo_padrinho(api, nome))
    gerar(api, "2026-10")
    gerar(api, "2026-11")

    ordem = [(c["competencia"], c["padrinho"]["nome"]) for c in cobrancas(api)]

    assert ordem == [
        ("2026-11-01", "Alfa"),
        ("2026-11-01", "Zeta"),
        ("2026-10-01", "Alfa"),
        ("2026-10-01", "Zeta"),
    ]


def test_filtros_de_situacao(api, novo_aluno, monkeypatch):
    # quatro empresas, uma em cada situação, hoje = 20/11
    nomes = ["Aberta", "Atrasada", "Paga", "Cancelada", "Vencendo"]
    empresas = {n: novo_padrinho(api, n, emitir_ate_dia=10) for n in nomes}
    for empresa in empresas.values():
        apadrinhar(api, novo_aluno(), empresa)
    gerar(api)
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 20))
    por_nome = {c["padrinho"]["nome"]: c["id"] for c in cobrancas(api)}
    emitir(api, por_nome["Atrasada"], numero="N1", emissao="2026-11-01", vencimento="2026-11-15")
    emitir(api, por_nome["Vencendo"], numero="N2", emissao="2026-11-01", vencimento="2026-11-20")
    emitir(api, por_nome["Paga"], numero="N3", emissao="2026-11-01", vencimento="2026-11-25")
    pagar(api, por_nome["Paga"], valor_pago="150.00")
    api.patch(f"/api/cobrancas/{por_nome['Cancelada']}/cancelar", json={"motivo": "Teste"})

    def nomes_de(situacao):
        return sorted(c["padrinho"]["nome"] for c in cobrancas(api, situacao=situacao))

    assert nomes_de("todas") == sorted(nomes)
    assert nomes_de("a_emitir") == ["Aberta"]
    assert nomes_de("emissao_atrasada") == ["Aberta"]  # prazo dia 10, hoje dia 20
    assert nomes_de("a_vencer") == ["Vencendo"]  # vence hoje: ainda não está atrasada
    assert nomes_de("atrasada") == ["Atrasada"]
    assert nomes_de("paga") == ["Paga"]
    assert nomes_de("cancelada") == ["Cancelada"]


@pytest.mark.parametrize(
    "parametros",
    [
        {"situacao": "qualquer"},
        {"situacao": "emitida"},
        {"mes": "2026-13"},
        {"mes": "novembro"},
        {"mes": "2026-11-31"},
        {"padrinho_id": "0"},
        {"padrinho_id": "-1"},
        {"padrinho_id": "2147483648"},
        {"padrinho_id": "abc"},
    ],
)
def test_filtros_invalidos_dao_422(api, parametros):
    assert api.get("/api/cobrancas", params=parametros).status_code == 422


def test_filtro_de_mes_invalido_sai_no_formato_dos_outros_erros(api):
    corpo = api.get("/api/cobrancas", params={"mes": "xx"}).json()

    assert corpo["detail"][0]["loc"] == ["query", "mes"]


def test_a_resposta_nao_traz_dados_pessoais_alem_do_necessario(api, cobranca):
    texto = str(cobranca)

    assert "telefone" not in texto and "email" not in texto and "cnpj" not in texto
    assert set(cobranca["padrinho"]) == {"id", "nome", "ativo"}
    assert set(cobranca["alunos"][0]["aluno"]) == {"id", "nome", "ativo"}


def test_aluno_inativo_continua_na_cobranca(api, novo_aluno):
    padrinho = novo_padrinho(api)
    aluno = novo_aluno("Inativado")
    apadrinhar(api, aluno, padrinho)
    gerar(api)
    api.put(
        f"/api/alunos/{aluno['id']}",
        json={**aluno, "ativo": False, "responsavel_ids": [r["id"] for r in aluno["responsaveis"]]},
    )

    item = cobrancas(api)[0]["alunos"][0]

    assert item["aluno"]["nome"] == "Inativado"


# ---------- Quantidade de consultas (sem uma por linha) ----------


def contar_consultas(cliente, db) -> int:
    db.expire_all()  # esquece o que a sessão de teste já tem, para uma consulta por linha aparecer
    total = 0

    def conta(*_):
        nonlocal total
        total += 1

    event.listen(engine, "before_cursor_execute", conta)
    try:
        assert cliente.get("/api/cobrancas").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", conta)
    return total


def test_a_lista_nao_faz_uma_consulta_por_cobranca(api, api_como, db, novo_aluno):
    def nova_cobranca(i, paga=False):
        empresa = novo_padrinho(api, f"Empresa {i}")
        apadrinhar(api, novo_aluno(f"Aluno {i}a"), empresa)
        apadrinhar(api, novo_aluno(f"Aluno {i}b"), empresa)
        gerar(api)
        if paga:
            aberta = next(c for c in cobrancas(api) if c["padrinho"]["id"] == empresa["id"])
            api_como(Perfil.OPERADOR)  # cada passo é feito por um usuário diferente
            assert (
                emitir(api_como(Perfil.OPERADOR), aberta["id"], numero=f"N{i}").status_code == 200
            )
            assert (
                pagar(api_como(Perfil.OPERADOR), aberta["id"], valor_pago="300.00").status_code
                == 201
            )

    for i in range(2):
        nova_cobranca(i, paga=True)
    com_2 = contar_consultas(api, db)
    for i in range(2, 7):
        nova_cobranca(i, paga=True)

    assert len(cobrancas(api)) == 7
    assert contar_consultas(api, db) == com_2


# ---------- O banco também garante as regras (RNF08) ----------


def cobranca_no_banco(db, cobranca: dict, **mudancas) -> None:
    sets = ", ".join(f"{campo} = :{campo}" for campo in mudancas)
    db.execute(
        text(f"UPDATE cobrancas SET {sets} WHERE id = :id"), {**mudancas, "id": cobranca["id"]}
    )


@pytest.mark.parametrize(
    "mudancas, restricao",
    [
        ({"valor": 0}, "valor_positivo"),
        ({"competencia": date(2026, 11, 2)}, "competencia_dia_um"),
        ({"data_vencimento": date(2026, 10, 31)}, "vencimento_depois_da_competencia"),
        ({"limite_emissao": date(2026, 10, 31)}, "limite_depois_da_competencia"),
        ({"status": "emitida"}, "emitida_com_nota"),
        ({"status": "paga"}, "emitida_com_nota"),
        ({"status": "cancelada"}, "cancelada_com_motivo"),
        ({"numero_nota": "NF-1"}, "a_emitir_sem_nota"),
        ({"status": "qualquer"}, "status"),
    ],
)
def test_banco_recusa_cobranca_fora_das_regras(api, db, cobranca, mudancas, restricao):
    with pytest.raises(IntegrityError, match=restricao):
        cobranca_no_banco(db, cobranca, **mudancas)


def test_banco_recusa_vencimento_antes_da_emissao(api, db, emitida):
    with pytest.raises(IntegrityError, match="vencimento_depois_da_emissao"):
        cobranca_no_banco(db, emitida, data_vencimento=date(2026, 11, 2))


def test_banco_recusa_duas_cobrancas_abertas_da_mesma_empresa_no_mes(api, db, cobranca):
    with pytest.raises(IntegrityError, match="uq_cobrancas_padrinho_competencia_a_emitir"):
        db.execute(
            text(
                "INSERT INTO cobrancas (padrinho_id, competencia, valor, status, data_vencimento,"
                " criado_por_id) SELECT padrinho_id, competencia, 10, 'a_emitir', data_vencimento,"
                " criado_por_id FROM cobrancas WHERE id = :id"
            ),
            {"id": cobranca["id"]},
        )


def test_banco_aceita_uma_cobranca_aberta_ao_lado_de_uma_emitida(api, db, emitida):
    db.execute(
        text(
            "INSERT INTO cobrancas (padrinho_id, competencia, valor, status, data_vencimento,"
            " criado_por_id) SELECT padrinho_id, competencia, 10, 'a_emitir', data_vencimento,"
            " criado_por_id FROM cobrancas WHERE id = :id"
        ),
        {"id": emitida["id"]},
    )
    assert db.scalar(text("SELECT count(*) FROM cobrancas")) == 2


def test_banco_recusa_numero_de_nota_repetido_ate_com_outras_maiusculas(
    api, db, emitida, novo_aluno
):
    outra = novo_padrinho(api, "Beta Engenharia")
    apadrinhar(api, novo_aluno(), outra)
    gerar(api)
    segunda = next(c for c in cobrancas(api) if c["padrinho"]["nome"] == "Beta Engenharia")
    with pytest.raises(IntegrityError, match="uq_cobrancas_numero_nota"):
        db.execute(
            text(
                "UPDATE cobrancas SET numero_nota = 'nf-100', data_emissao = '2026-11-03',"
                " emitida_por_id = criado_por_id, emitida_em = now(), status = 'emitida'"
                " WHERE id = :id"
            ),
            {"id": segunda["id"]},
        )


def test_banco_recusa_dois_pagamentos_ativos_na_mesma_cobranca(api, db, paga):
    with pytest.raises(IntegrityError, match="uq_pagamentos_cobranca_ativo"):
        db.execute(
            text(
                "INSERT INTO pagamentos_cobranca (cobranca_id, data_pagamento, valor_pago,"
                " forma_pagamento, criado_por_id) SELECT cobranca_id, data_pagamento, 1,"
                " forma_pagamento, criado_por_id FROM pagamentos_cobranca"
            )
        )


def test_banco_aceita_novo_pagamento_depois_de_cancelar_o_anterior(api, db, paga):
    db.execute(
        text(
            "UPDATE pagamentos_cobranca SET cancelado_em = now(),"
            " motivo_cancelamento = 'Lançado em dobro', cancelado_por_id = criado_por_id"
        )
    )
    db.execute(
        text(
            "INSERT INTO pagamentos_cobranca (cobranca_id, data_pagamento, valor_pago,"
            " forma_pagamento, criado_por_id) SELECT cobranca_id, data_pagamento, 1,"
            " forma_pagamento, criado_por_id FROM pagamentos_cobranca"
        )
    )
    assert db.scalar(text("SELECT count(*) FROM pagamentos_cobranca")) == 2


@pytest.mark.parametrize(
    "coluna, valor, restricao",
    [("valor_pago", 0, "valor_positivo"), ("forma_pagamento", "dinheiro", "forma_pagamento")],
)
def test_banco_recusa_pagamento_da_cobranca_invalido(api, db, paga, coluna, valor, restricao):
    with pytest.raises(IntegrityError, match=restricao):
        db.execute(text(f"UPDATE pagamentos_cobranca SET {coluna} = :v"), {"v": valor})


def test_banco_recusa_mensalidade_de_cobranca_que_nao_existe(api, db, cobranca):
    with pytest.raises(IntegrityError, match="fk_mensalidades_cobranca_id_cobrancas"):
        db.execute(
            text("UPDATE mensalidades SET cobranca_id = 999999 WHERE cobranca_id = :id"),
            {"id": cobranca["id"]},
        )
