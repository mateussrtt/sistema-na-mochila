from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, event, select, update

from app.core import tempo
from app.db.session import engine
from app.models import (
    Aluno,
    Mensalidade,
    Perfil,
    StatusMensalidade,
    Usuario,
    aluno_responsavel,
)

HOJE = date(2026, 11, 5)


@pytest.fixture(autouse=True)
def relogio(monkeypatch):
    """Todos os testes rodam "em 5 de novembro de 2026". Dá para mudar o dia dentro do teste."""
    dia = {"hoje": HOJE}
    monkeypatch.setattr(tempo, "hoje", lambda: dia["hoje"])
    return dia


# ---------- Montagem do cenário ----------


def novo_responsavel(api, nome="Ana Prado", telefone="31977776666", email=None) -> dict:
    corpo = {"nome": nome, "telefone": telefone, "email": email}
    resposta = api.post("/api/responsaveis", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def novo_aluno(api, nome, responsaveis, **campos) -> dict:
    corpo = {"nome": nome, "responsavel_ids": [r["id"] for r in responsaveis]} | campos
    resposta = api.post("/api/alunos", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def matricular(api, aluno, valor="150.00", inicio="2026-01-15", **campos) -> dict:
    corpo = {"aluno_id": aluno["id"], "data_inicio": inicio, "valor_mensalidade": valor} | campos
    resposta = api.post("/api/matriculas", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def gerar(api, *meses):
    for mes in meses:
        assert api.post("/api/mensalidades/gerar", json={"competencia": mes}).status_code == 200


def aluno_em_atraso(api, nome="Pedro Souza", valor="150.00", responsaveis=None, **campos) -> dict:
    """Cria responsável (se não vier), aluno e matrícula. Devolve o aluno."""
    responsaveis = responsaveis or [novo_responsavel(api)]
    aluno = novo_aluno(api, nome, responsaveis)
    matricular(api, aluno, valor, **campos)
    return aluno


def pendencias(cliente, **parametros) -> dict:
    resposta = cliente.get("/api/pendencias", params=parametros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {str(e["loc"][-1]): e["msg"] for e in resposta.json()["detail"]}


def mensalidades_do_banco(db) -> list[Mensalidade]:
    return list(db.scalars(select(Mensalidade).order_by(Mensalidade.id)))


def nomes_dos_alunos(painel) -> list[str]:
    return [a["nome"] for g in painel["grupos"] for a in g["alunos"]]


def nomes_dos_responsaveis(grupo) -> list[str]:
    return [r["nome"] for r in grupo["responsaveis"]]


# ---------- O painel ----------


def test_sem_pendencias_o_painel_vem_vazio(api):
    assert pendencias(api) == {
        "mes": None,
        "resumo": {"responsaveis": 0, "alunos": 0, "mensalidades": 0, "total_em_aberto": "0.00"},
        "grupos": [],
    }


def test_lista_o_responsavel_com_o_aluno_e_o_mes_em_atraso(api):
    responsavel = novo_responsavel(api, "Maria Souza", "31988887777", "maria@exemplo.com")
    aluno = aluno_em_atraso(api, "Pedro Souza", responsaveis=[responsavel])
    gerar(api, "2026-10")

    painel = pendencias(api)

    assert painel["resumo"] == {
        "responsaveis": 1,
        "alunos": 1,
        "mensalidades": 1,
        "total_em_aberto": "150.00",
    }
    (grupo,) = painel["grupos"]
    assert grupo["responsaveis"] == [
        {
            "id": responsavel["id"],
            "nome": "Maria Souza",
            "telefone": "31988887777",
            "email": "maria@exemplo.com",
        }
    ]
    assert grupo["total"] == "150.00"
    assert grupo["maior_atraso"] == 26  # venceu em 10/10 e hoje é 05/11
    (do_aluno,) = grupo["alunos"]
    assert do_aluno["id"] == aluno["id"]
    assert do_aluno["nome"] == "Pedro Souza"
    assert do_aluno["ativo"] is True
    assert do_aluno["total"] == "150.00"
    (mensalidade,) = do_aluno["mensalidades"]
    assert mensalidade["competencia"] == "2026-10-01"
    assert mensalidade["valor"] == "150.00"
    assert mensalidade["data_vencimento"] == "2026-10-10"
    assert mensalidade["dias_em_atraso"] == 26


# ---------- Quando conta como atraso (RN07) ----------


def test_no_dia_do_vencimento_ainda_nao_esta_atrasada_e_no_dia_11_esta(api, relogio):
    aluno_em_atraso(api)
    gerar(api, "2026-11")  # vence em 10/11

    relogio["hoje"] = date(2026, 11, 9)
    assert pendencias(api)["grupos"] == []
    relogio["hoje"] = date(2026, 11, 10)
    assert pendencias(api)["grupos"] == []
    relogio["hoje"] = date(2026, 11, 11)
    painel = pendencias(api)
    assert painel["resumo"]["mensalidades"] == 1
    assert painel["grupos"][0]["maior_atraso"] == 1


def test_mensalidade_a_vencer_nao_entra(api):
    aluno_em_atraso(api)
    gerar(api, "2026-11")  # hoje é 05/11, vence dia 10
    assert pendencias(api)["resumo"]["mensalidades"] == 0


def test_quem_entrou_depois_do_dia_10_so_atrasa_depois_da_data_de_inicio(api, relogio):
    aluno_em_atraso(api, inicio="2026-10-20")
    gerar(api, "2026-10")  # vence em 20/10, a data de início
    relogio["hoje"] = date(2026, 10, 20)
    assert pendencias(api)["grupos"] == []
    relogio["hoje"] = date(2026, 10, 21)
    assert pendencias(api)["resumo"]["mensalidades"] == 1


def test_mensalidade_paga_nao_entra(api):
    aluno_em_atraso(api)
    gerar(api, "2026-10")
    id_ = api.get("/api/mensalidades", params={"mes": "2026-10"}).json()[0]["id"]
    assert pendencias(api)["resumo"]["mensalidades"] == 1

    pagamento = {"data_pagamento": "2026-11-05", "valor_pago": "150.00", "forma_pagamento": "pix"}
    assert api.post(f"/api/mensalidades/{id_}/pagamento", json=pagamento).status_code == 201

    assert pendencias(api)["grupos"] == []


@pytest.mark.parametrize("status", [StatusMensalidade.ISENTA, StatusMensalidade.CANCELADA])
def test_isenta_e_cancelada_nao_entram(api, db, status):
    aluno_em_atraso(api)
    gerar(api, "2026-10")
    id_ = api.get("/api/mensalidades", params={"mes": "2026-10"}).json()[0]["id"]
    acao = "isentar" if status == StatusMensalidade.ISENTA else "cancelar"
    alteracao = api.patch(f"/api/mensalidades/{id_}/{acao}", json={"motivo": "Motivo de teste"})
    assert alteracao.status_code == 200
    assert pendencias(api)["resumo"]["mensalidades"] == 0
    assert pendencias(api)["grupos"] == []


def test_so_as_pendentes_vencidas_entram_no_meio_de_varias(api, db):
    """Cinco alunos, cinco situações diferentes: só o pendente vencido aparece."""
    nomes = ["Ana Atrasada", "Beto Pago", "Carla Isenta", "Davi Cancelado", "Edu AVencer"]
    for nome in nomes:
        aluno_em_atraso(api, nome)
    gerar(api, "2026-10")
    por_nome = {m["aluno"]["nome"]: m["id"] for m in api.get("/api/mensalidades").json()}
    pagamento = {"data_pagamento": "2026-11-01", "valor_pago": "150.00", "forma_pagamento": "pix"}
    api.post(f"/api/mensalidades/{por_nome['Beto Pago']}/pagamento", json=pagamento)
    for nome, status in (
        ("Carla Isenta", StatusMensalidade.ISENTA),
        ("Davi Cancelado", StatusMensalidade.CANCELADA),
    ):
        acao = "isentar" if status == StatusMensalidade.ISENTA else "cancelar"
        alteracao = api.patch(
            f"/api/mensalidades/{por_nome[nome]}/{acao}", json={"motivo": "Motivo de teste"}
        )
        assert alteracao.status_code == 200
    # Edu ainda vai vencer: muda o vencimento direto no banco
    db.execute(
        update(Mensalidade)
        .where(Mensalidade.id == por_nome["Edu AVencer"])
        .values(data_vencimento=date(2026, 11, 20))
    )
    db.flush()

    assert nomes_dos_alunos(pendencias(api)) == ["Ana Atrasada"]


# ---------- Mais de um mês e valores ----------


@pytest.mark.parametrize("ordem", [("2026-09", "2026-10"), ("2026-10", "2026-09")])
def test_aluno_com_varios_meses_em_aberto_lista_todos_em_ordem(api, ordem):
    """Não importa em que ordem os meses foram gerados: a lista e o maior atraso valem igual."""
    aluno_em_atraso(api)
    gerar(api, *ordem)

    (grupo,) = pendencias(api)["grupos"]
    (aluno,) = grupo["alunos"]
    assert [m["competencia"] for m in aluno["mensalidades"]] == ["2026-09-01", "2026-10-01"]
    assert [m["dias_em_atraso"] for m in aluno["mensalidades"]] == [56, 26]
    assert aluno["total"] == "300.00"
    assert grupo["total"] == "300.00"
    assert grupo["maior_atraso"] == 56


def test_soma_com_centavos_sem_erro_de_arredondamento(api):
    responsavel = novo_responsavel(api)
    for nome, valor in (("Aluno A", "150.10"), ("Aluno B", "99.95"), ("Aluno C", "0.01")):
        matricular(api, novo_aluno(api, nome, [responsavel]), valor)
    gerar(api, "2026-10")

    painel = pendencias(api)
    assert painel["resumo"]["total_em_aberto"] == "250.06"
    assert painel["grupos"][0]["total"] == "250.06"


def test_valor_da_mensalidade_e_o_da_matricula_mesmo_com_bolsa_parcial(api):
    aluno_em_atraso(api, valor="80.00", bolsa="parcial")
    gerar(api, "2026-10")
    assert pendencias(api)["resumo"]["total_em_aberto"] == "80.00"


def test_bolsista_integral_nao_aparece(api):
    aluno_em_atraso(api, valor="", bolsa="integral")
    gerar(api, "2026-10")
    assert pendencias(api)["resumo"]["mensalidades"] == 0


def test_valores_grandes_somam_sem_estourar(api):
    responsavel = novo_responsavel(api)
    for nome in ("Aluno A", "Aluno B"):
        matricular(api, novo_aluno(api, nome, [responsavel]), "99999999.99")
    gerar(api, "2026-10")
    assert pendencias(api)["resumo"]["total_em_aberto"] == "199999999.98"


# ---------- Um cartão por pendência: os alunos com os mesmos responsáveis ----------


def test_irmaos_do_mesmo_responsavel_ficam_num_grupo_so(api):
    responsavel = novo_responsavel(api)
    for nome in ("Zeca Prado", "Ana Prado"):
        matricular(api, novo_aluno(api, nome, [responsavel]))
    gerar(api, "2026-10")

    painel = pendencias(api)
    assert painel["resumo"] == {
        "responsaveis": 1,
        "alunos": 2,
        "mensalidades": 2,
        "total_em_aberto": "300.00",
    }
    (grupo,) = painel["grupos"]
    assert [a["nome"] for a in grupo["alunos"]] == ["Ana Prado", "Zeca Prado"]
    assert grupo["total"] == "300.00"


def test_aluno_com_dois_responsaveis_aparece_uma_vez_com_os_dois_no_mesmo_grupo(api):
    pai = novo_responsavel(api, "Pai Souza", "31933334444")
    mae = novo_responsavel(api, "Mãe Souza", "31911112222", "mae@exemplo.com")
    aluno_em_atraso(api, "Pedro Souza", responsaveis=[pai, mae])
    gerar(api, "2026-10")

    painel = pendencias(api)

    (grupo,) = painel["grupos"]
    # Os responsáveis ficam um abaixo do outro, em ordem de nome, cada um com o seu contato
    assert grupo["responsaveis"] == [
        {
            "id": mae["id"],
            "nome": "Mãe Souza",
            "telefone": "31911112222",
            "email": "mae@exemplo.com",
        },
        {"id": pai["id"], "nome": "Pai Souza", "telefone": "31933334444", "email": None},
    ]
    assert [a["nome"] for a in grupo["alunos"]] == ["Pedro Souza"]
    assert grupo["total"] == "150.00"
    # Nada é contado em dobro
    assert painel["resumo"] == {
        "responsaveis": 2,
        "alunos": 1,
        "mensalidades": 1,
        "total_em_aberto": "150.00",
    }


def test_irmaos_com_os_mesmos_dois_responsaveis_ficam_num_cartao_so(api):
    """A ordem em que os responsáveis foram informados no cadastro não separa os irmãos."""
    mae = novo_responsavel(api, "Mãe Souza", "31911112222")
    pai = novo_responsavel(api, "Pai Souza", "31933334444")
    matricular(api, novo_aluno(api, "Pedro Souza", [mae, pai]))
    matricular(api, novo_aluno(api, "Laura Souza", [pai, mae]))
    gerar(api, "2026-10")

    painel = pendencias(api)
    (grupo,) = painel["grupos"]
    assert nomes_dos_responsaveis(grupo) == ["Mãe Souza", "Pai Souza"]
    assert [a["nome"] for a in grupo["alunos"]] == ["Laura Souza", "Pedro Souza"]
    assert painel["resumo"]["responsaveis"] == 2
    assert painel["resumo"]["alunos"] == 2


def test_meio_irmaos_viram_dois_cartoes_e_nenhuma_cobranca_se_repete(api):
    """A mãe é a mesma, mas o Pedro é só dela e a Bia também é filha do Paulo."""
    maria = novo_responsavel(api, "Maria Souza", "31988887777")
    paulo = novo_responsavel(api, "Paulo Lima", "31955554444")
    matricular(api, novo_aluno(api, "Pedro Souza", [maria]), "150.00")
    matricular(api, novo_aluno(api, "Bia Lima", [maria, paulo]), "100.00")
    gerar(api, "2026-10")

    painel = pendencias(api)

    assert len(painel["grupos"]) == 2
    por_responsaveis = {tuple(nomes_dos_responsaveis(g)): g for g in painel["grupos"]}
    assert [a["nome"] for a in por_responsaveis[("Maria Souza",)]["alunos"]] == ["Pedro Souza"]
    assert [a["nome"] for a in por_responsaveis[("Maria Souza", "Paulo Lima")]["alunos"]] == [
        "Bia Lima"
    ]
    # Cada aluno aparece uma vez só, e a soma dos cartões é exatamente o total em aberto
    assert sorted(nomes_dos_alunos(painel)) == ["Bia Lima", "Pedro Souza"]
    soma = sum(Decimal(g["total"]) for g in painel["grupos"])
    assert soma == Decimal(painel["resumo"]["total_em_aberto"]) == Decimal("250.00")
    # E a Maria, que aparece em dois cartões, é contada como uma pessoa só
    assert painel["resumo"]["responsaveis"] == 2


def test_a_soma_dos_cartoes_e_sempre_o_total_em_aberto(api):
    """Um cenário misto: irmãos, pai e mãe, meio-irmãos, filho único e vários meses."""
    mae = novo_responsavel(api, "Mãe A", "31911110001")
    pai = novo_responsavel(api, "Pai A", "31911110002")
    outra = novo_responsavel(api, "Outra B", "31911110003")
    sozinho = novo_responsavel(api, "Sozinho C", "31911110004")
    matricular(api, novo_aluno(api, "Irmão 1", [mae, pai]), "110.10")
    matricular(api, novo_aluno(api, "Irmão 2", [mae, pai]), "120.20")
    matricular(api, novo_aluno(api, "Meio-irmão", [mae]), "130.30")
    matricular(api, novo_aluno(api, "Filha de B", [outra]), "99.99")
    matricular(api, novo_aluno(api, "Filho de C", [sozinho, outra]), "0.01")
    gerar(api, "2026-08", "2026-09", "2026-10")

    painel = pendencias(api)

    ids = [a["id"] for g in painel["grupos"] for a in g["alunos"]]
    assert len(ids) == len(set(ids)) == painel["resumo"]["alunos"] == 5
    soma_grupos = sum(Decimal(g["total"]) for g in painel["grupos"])
    soma_alunos = sum(Decimal(a["total"]) for g in painel["grupos"] for a in g["alunos"])
    assert soma_grupos == soma_alunos == Decimal(painel["resumo"]["total_em_aberto"])
    assert painel["resumo"]["mensalidades"] == 15
    assert painel["resumo"]["responsaveis"] == 4


def test_maior_atraso_do_cartao_e_o_do_aluno_mais_atrasado(api):
    responsavel = novo_responsavel(api)
    antigo = novo_aluno(api, "Aluno Antigo", [responsavel])
    novo = novo_aluno(api, "Aluno Novo", [responsavel])
    matricular(api, antigo, inicio="2026-01-15")
    matricular(api, novo, inicio="2026-10-01")
    gerar(api, "2026-09", "2026-10")  # só o aluno antigo deve a de setembro

    (grupo,) = pendencias(api)["grupos"]
    por_nome = {a["nome"]: a for a in grupo["alunos"]}
    assert len(por_nome["Aluno Antigo"]["mensalidades"]) == 2
    assert len(por_nome["Aluno Novo"]["mensalidades"]) == 1
    assert grupo["maior_atraso"] == 56


def test_dois_responsaveis_com_o_mesmo_nome_continuam_em_cartoes_separados(api):
    primeiro = novo_responsavel(api, "Maria Silva", "31911112222")
    segundo = novo_responsavel(api, "Maria Silva", "31933334444")
    aluno_em_atraso(api, "Aluno Um", responsaveis=[primeiro])
    aluno_em_atraso(api, "Aluno Dois", responsaveis=[segundo])
    gerar(api, "2026-10")

    grupos = pendencias(api)["grupos"]
    assert len(grupos) == 2
    assert {g["responsaveis"][0]["telefone"] for g in grupos} == {"31911112222", "31933334444"}


def test_dois_alunos_com_o_mesmo_nome_continuam_separados(api):
    responsavel = novo_responsavel(api)
    for _ in range(2):
        matricular(api, novo_aluno(api, "João Lima", [responsavel]))
    gerar(api, "2026-10")

    (grupo,) = pendencias(api)["grupos"]
    assert len(grupo["alunos"]) == 2
    assert len({a["id"] for a in grupo["alunos"]}) == 2


def test_ordem_por_maior_atraso_e_depois_por_nome_dos_responsaveis(api, db):
    # A Bia é cadastrada antes da Ana: no empate, vale o nome e não a ordem de cadastro
    igual_a = novo_responsavel(api, "Bia Igual", "31955556666")
    antigo = novo_responsavel(api, "Zélia Antiga", "31933334444")
    recente = novo_responsavel(api, "Ana Recente", "31911112222")
    aluno_em_atraso(api, "Filho Recente", responsaveis=[recente])
    aluno_em_atraso(api, "Filho Antigo", responsaveis=[antigo])
    aluno_em_atraso(api, "Filho Igual", responsaveis=[igual_a])
    gerar(api, "2026-10")
    por_aluno = {m["aluno"]["nome"]: m["id"] for m in api.get("/api/mensalidades").json()}
    # a mensalidade do Filho Antigo venceu em 01/10: 35 dias; as outras duas, 26 dias
    db.execute(
        update(Mensalidade)
        .where(Mensalidade.id == por_aluno["Filho Antigo"])
        .values(data_vencimento=date(2026, 10, 1))
    )
    db.flush()

    grupos = pendencias(api)["grupos"]
    # Zélia (35 dias) primeiro; Ana e Bia empatam em 26 dias e saem por nome
    assert [nomes_dos_responsaveis(g) for g in grupos] == [
        ["Zélia Antiga"],
        ["Ana Recente"],
        ["Bia Igual"],
    ]


# ---------- Filtro por mês ----------


def montar_tres_meses(api):
    aluno_em_atraso(api)
    gerar(api, "2026-08", "2026-09", "2026-10")


def test_sem_mes_mostra_todos_os_meses(api):
    montar_tres_meses(api)
    painel = pendencias(api)
    assert painel["mes"] is None
    assert painel["resumo"]["mensalidades"] == 3
    assert painel["resumo"]["total_em_aberto"] == "450.00"


def test_filtra_por_um_mes(api):
    montar_tres_meses(api)
    painel = pendencias(api, mes="2026-09")
    assert painel["mes"] == "2026-09-01"
    assert painel["resumo"]["mensalidades"] == 1
    (mensalidade,) = painel["grupos"][0]["alunos"][0]["mensalidades"]
    assert mensalidade["competencia"] == "2026-09-01"
    assert painel["grupos"][0]["maior_atraso"] == 56


def test_mes_sem_pendencia_devolve_painel_vazio(api):
    montar_tres_meses(api)
    painel = pendencias(api, mes="2026-07")
    assert painel["mes"] == "2026-07-01"
    assert painel["resumo"]["mensalidades"] == 0
    assert painel["grupos"] == []


def test_mes_atual_ainda_nao_vencido_vem_vazio(api):
    montar_tres_meses(api)
    gerar(api, "2026-11")
    assert pendencias(api, mes="2026-11")["grupos"] == []


def test_aceita_o_mes_com_dia_e_normaliza_para_o_dia_1(api):
    montar_tres_meses(api)
    painel = pendencias(api, mes="2026-10-27")
    assert painel["mes"] == "2026-10-01"
    assert painel["resumo"]["mensalidades"] == 1


@pytest.mark.parametrize("mes", ["", "   "])
def test_mes_em_branco_vale_como_todos_os_meses(api, mes):
    montar_tres_meses(api)
    painel = pendencias(api, mes=mes)
    assert painel["mes"] is None
    assert painel["resumo"]["mensalidades"] == 3


@pytest.mark.parametrize(
    "mes",
    ["2026-13", "2026-00", "abc", "2026-1", "202610", "2026/10", "2026-10-32", "2026-02-30", "-1"],
)
def test_mes_invalido_da_422_em_portugues(api, mes):
    erros = erros_de(api.get("/api/pendencias", params={"mes": mes}))
    assert erros["mes"] == "Informe o mês no formato AAAA-MM"


def test_mes_comprido_demais_da_422(api):
    assert api.get("/api/pendencias", params={"mes": "2026-10-0100"}).status_code == 422


def test_mes_com_digitos_de_outro_alfabeto_e_recusado(api):
    assert api.get("/api/pendencias", params={"mes": "٢٠٢٦-١٠"}).status_code == 422


def test_mes_com_caractere_nulo_e_com_injecao_nao_quebram(api):
    for mes in ("2026-10" + chr(0), "2026-10'; DROP TABLE mensalidades;--"):
        resposta = api.get("/api/pendencias", params={"mes": mes})
        assert resposta.status_code == 422
    assert pendencias(api)["resumo"]["mensalidades"] == 0


# ---------- Quem aparece na lista ----------


def test_aluno_inativo_continua_na_lista_enquanto_deve(api, db):
    aluno = aluno_em_atraso(api, "Pedro Souza")
    gerar(api, "2026-10")
    db.execute(update(Aluno).where(Aluno.id == aluno["id"]).values(ativo=False))
    db.flush()

    (grupo,) = pendencias(api)["grupos"]
    assert grupo["alunos"][0]["nome"] == "Pedro Souza"
    assert grupo["alunos"][0]["ativo"] is False


def test_matricula_encerrada_nao_perdoa_a_mensalidade_ja_gerada(api):
    responsavel = novo_responsavel(api)
    aluno = novo_aluno(api, "Pedro Souza", [responsavel])
    matricula = matricular(api, aluno)
    gerar(api, "2026-10")
    api.patch(
        f"/api/matriculas/{matricula['id']}/encerrar", json={"data_encerramento": "2026-10-20"}
    )

    assert pendencias(api)["resumo"]["mensalidades"] == 1


def test_responsavel_so_com_email_vem_sem_telefone(api):
    responsavel = novo_responsavel(api, "Rita Alves", telefone=None, email="rita@exemplo.com")
    aluno_em_atraso(api, responsaveis=[responsavel])
    gerar(api, "2026-10")

    (grupo,) = pendencias(api)["grupos"]
    assert grupo["responsaveis"][0]["telefone"] is None
    assert grupo["responsaveis"][0]["email"] == "rita@exemplo.com"


def test_responsavel_sem_alunos_em_atraso_nao_aparece(api):
    novo_responsavel(api, "Sem Dívida", "31900000000")
    devedor = novo_responsavel(api, "Devedor", "31911111111")
    aluno_em_atraso(api, "Com Dívida", responsaveis=[devedor])
    gerar(api, "2026-10")

    (grupo,) = pendencias(api)["grupos"]
    assert nomes_dos_responsaveis(grupo) == ["Devedor"]


def test_aluno_sem_mensalidade_gerada_nao_aparece(api):
    aluno_em_atraso(api)
    assert pendencias(api)["grupos"] == []


def test_aluno_sem_responsavel_nao_some_da_lista(api, db):
    """Não deveria existir (RN01), mas se o vínculo se perder a dívida continua visível."""
    aluno = aluno_em_atraso(api, "Pedro Souza")
    gerar(api, "2026-10")
    db.execute(delete(aluno_responsavel).where(aluno_responsavel.c.aluno_id == aluno["id"]))
    db.flush()

    painel = pendencias(api)

    (grupo,) = painel["grupos"]
    assert grupo["responsaveis"] == []
    assert [a["nome"] for a in grupo["alunos"]] == ["Pedro Souza"]
    assert painel["resumo"]["alunos"] == 1
    assert painel["resumo"]["responsaveis"] == 0
    assert painel["resumo"]["total_em_aberto"] == "150.00"


# ---------- Pagou, sai da lista (integração com o pagamento) ----------


def test_pagar_uma_de_duas_mensalidades_mantem_a_outra(api):
    aluno_em_atraso(api)
    gerar(api, "2026-09", "2026-10")
    setembro = api.get("/api/mensalidades", params={"mes": "2026-09"}).json()[0]["id"]
    pagamento = {"data_pagamento": "2026-11-05", "valor_pago": "150.00", "forma_pagamento": "pix"}
    api.post(f"/api/mensalidades/{setembro}/pagamento", json=pagamento)

    painel = pendencias(api)
    assert painel["resumo"]["mensalidades"] == 1
    assert painel["resumo"]["total_em_aberto"] == "150.00"
    assert painel["grupos"][0]["alunos"][0]["mensalidades"][0]["competencia"] == "2026-10-01"


# ---------- Permissões e privacidade ----------


def test_sem_login_nao_ve_o_painel(sem_login):
    assert sem_login.get("/api/pendencias").status_code == 401


def test_token_invalido_nao_ve_o_painel(sem_login):
    resposta = sem_login.get("/api/pendencias", headers={"Authorization": "Bearer invalido"})
    assert resposta.status_code == 401


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_veem_o_painel(api, api_como, perfil):
    aluno_em_atraso(api)
    gerar(api, "2026-10")
    assert pendencias(api_como(perfil))["resumo"]["mensalidades"] == 1


def test_usuario_desativado_nao_ve_o_painel(api, db, api_como):
    cliente = api_como(Perfil.CONSULTA)
    db.execute(update(Usuario).where(Usuario.email.like("consulta%")).values(ativo=False))
    db.flush()
    assert cliente.get("/api/pendencias").status_code == 401


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_o_painel_so_le(api, metodo):
    """Nada é criado, editado ou apagado por aqui (RN12)."""
    assert getattr(api, metodo)("/api/pendencias").status_code == 405


def test_resposta_traz_so_o_necessario_para_cobrar(api):
    responsavel = novo_responsavel(api, "Maria Souza", "31988887777", "maria@exemplo.com")
    aluno = novo_aluno(
        api,
        "Pedro Souza",
        [responsavel],
        escola="Escola Estadual Segredo",
        municipio="Cidade Reservada",
        data_nascimento="2014-03-09",
    )
    matricular(api, aluno)
    gerar(api, "2026-10")

    resposta = api.get("/api/pendencias")
    painel = resposta.json()
    assert set(painel) == {"mes", "resumo", "grupos"}
    assert set(painel["resumo"]) == {"responsaveis", "alunos", "mensalidades", "total_em_aberto"}
    grupo = painel["grupos"][0]
    assert set(grupo) == {"responsaveis", "alunos", "total", "maior_atraso"}
    assert set(grupo["responsaveis"][0]) == {"id", "nome", "telefone", "email"}
    assert set(grupo["alunos"][0]) == {"id", "nome", "ativo", "total", "mensalidades"}
    assert set(grupo["alunos"][0]["mensalidades"][0]) == {
        "id",
        "competencia",
        "valor",
        "data_vencimento",
        "dias_em_atraso",
    }
    # Dados do aluno que não servem para cobrar não saem (RN14, LGPD)
    for segredo in ("Segredo", "Reservada", "2014-03-09", "senha", "criado_por"):
        assert segredo not in resposta.text


# ---------- Só leitura e desempenho ----------


def test_consultar_o_painel_nao_altera_nada(api, db):
    aluno_em_atraso(api)
    gerar(api, "2026-09", "2026-10")
    antes = [(m.id, m.status, m.valor, m.data_vencimento) for m in mensalidades_do_banco(db)]

    for _ in range(3):
        pendencias(api)
        pendencias(api, mes="2026-10")

    depois = [(m.id, m.status, m.valor, m.data_vencimento) for m in mensalidades_do_banco(db)]
    assert antes == depois


def contar_consultas(cliente) -> int:
    total = 0

    def conta(*_):
        nonlocal total
        total += 1

    event.listen(engine, "before_cursor_execute", conta)
    try:
        assert cliente.get("/api/pendencias").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", conta)
    return total


def test_o_painel_nao_faz_uma_consulta_por_linha(api):
    aluno_em_atraso(api, "Aluno 00", responsaveis=[novo_responsavel(api, "Resp 00")])
    gerar(api, "2026-09", "2026-10")
    com_um = contar_consultas(api)

    for i in range(1, 9):
        aluno_em_atraso(
            api, f"Aluno {i:02d}", responsaveis=[novo_responsavel(api, f"Resp {i:02d}")]
        )
    gerar(api, "2026-09", "2026-10")
    com_nove = contar_consultas(api)

    assert pendencias(api)["resumo"]["alunos"] == 9
    assert com_nove == com_um
