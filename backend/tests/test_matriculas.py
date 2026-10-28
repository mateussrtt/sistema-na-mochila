from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Matricula
from app.routers import matriculas as rota_matriculas


@pytest.fixture
def aluno(api):
    responsavel = api.post(
        "/api/responsaveis", json={"nome": "Maria Souza", "telefone": "31988887777"}
    ).json()
    dados = {"nome": "Pedro Souza", "responsavel_ids": [responsavel["id"]]}
    return api.post("/api/alunos", json=dados).json()


def matricular(api, aluno_id, **campos):
    dados = {"aluno_id": aluno_id, "data_inicio": "2026-01-15", "valor_mensalidade": "150.00"}
    return api.post("/api/matriculas", json=dados | campos)


def encerrar(api, matricula_id, **campos):
    dados = {"data_encerramento": date.today().isoformat()} | campos
    return api.patch(f"/api/matriculas/{matricula_id}/encerrar", json=dados)


def test_matricula_aluno(api, aluno):
    resposta = matricular(api, aluno["id"])
    assert resposta.status_code == 201
    matricula = resposta.json()
    assert matricula["situacao"] == "ativa"
    assert matricula["data_inicio"] == "2026-01-15"
    assert matricula["data_encerramento"] is None
    assert matricula["valor_mensalidade"] == "150.00"
    assert matricula["aluno"]["nome"] == "Pedro Souza"


def test_valor_aceita_virgula_e_guarda_duas_casas(api, aluno):
    matricula = matricular(api, aluno["id"], valor_mensalidade="89,9").json()
    assert matricula["valor_mensalidade"] == "89.90"


@pytest.mark.parametrize("valor", ["0", "-10", "", "abc", "10.999", "100000000"])
def test_matricula_rejeita_valor_invalido(api, aluno, valor):
    assert matricular(api, aluno["id"], valor_mensalidade=valor).status_code == 422


def test_matricula_exige_valor(api, aluno):
    dados = {"aluno_id": aluno["id"], "data_inicio": "2026-01-15"}
    assert api.post("/api/matriculas", json=dados).status_code == 422


@pytest.mark.parametrize("data", ["", None, "31/11/2026"])
def test_matricula_exige_data_de_inicio(api, aluno, data):
    resposta = matricular(api, aluno["id"], data_inicio=data)
    assert resposta.status_code == 422


def test_matricula_rejeita_aluno_inexistente(api):
    assert matricular(api, 999999).status_code == 422


def test_matricula_rejeita_aluno_inativo(api, aluno):
    dados = {"nome": aluno["nome"], "responsavel_ids": [aluno["responsaveis"][0]["id"]]}
    api.put(f"/api/alunos/{aluno['id']}", json=dados | {"ativo": False})
    assert matricular(api, aluno["id"]).status_code == 422


def test_aluno_nao_tem_duas_matriculas_ativas(api, aluno):
    matricular(api, aluno["id"])
    assert matricular(api, aluno["id"]).status_code == 409


def test_encerra_matricula_sem_apagar(api, aluno):
    matricula = matricular(api, aluno["id"]).json()
    resposta = encerrar(api, matricula["id"])
    assert resposta.status_code == 200
    assert resposta.json()["situacao"] == "encerrada"
    assert resposta.json()["data_encerramento"] == date.today().isoformat()

    consultada = api.get(f"/api/matriculas/{matricula['id']}").json()
    assert consultada["valor_mensalidade"] == "150.00"
    assert consultada["situacao"] == "encerrada"


def test_encerra_matricula_so_uma_vez(api, aluno):
    matricula = matricular(api, aluno["id"]).json()
    encerrar(api, matricula["id"])
    assert encerrar(api, matricula["id"]).status_code == 409


def test_encerramento_nao_pode_ser_antes_do_inicio(api, aluno):
    matricula = matricular(api, aluno["id"], data_inicio="2026-01-15").json()
    assert encerrar(api, matricula["id"], data_encerramento="2026-01-14").status_code == 422


def test_encerramento_nao_pode_ser_no_futuro(api, aluno):
    matricula = matricular(api, aluno["id"]).json()
    amanha = (date.today() + timedelta(days=1)).isoformat()
    assert encerrar(api, matricula["id"], data_encerramento=amanha).status_code == 422


def test_encerramento_exige_data(api, aluno):
    matricula = matricular(api, aluno["id"]).json()
    assert encerrar(api, matricula["id"], data_encerramento="").status_code == 422


def test_aluno_pode_ser_matriculado_de_novo_depois_de_encerrar(api, aluno):
    primeira = matricular(api, aluno["id"]).json()
    encerrar(api, primeira["id"])
    segunda = matricular(api, aluno["id"], valor_mensalidade="120.00")
    assert segunda.status_code == 201

    todas = api.get("/api/matriculas", params={"situacao": "todas", "aluno_id": aluno["id"]})
    assert {m["id"] for m in todas.json()} == {primeira["id"], segunda.json()["id"]}


def test_lista_filtra_por_situacao_e_busca(api, aluno):
    ativa = matricular(api, aluno["id"]).json()
    outro = api.post(
        "/api/alunos",
        json={"nome": "Laura Dias", "responsavel_ids": [aluno["responsaveis"][0]["id"]]},
    ).json()
    encerrada = matricular(api, outro["id"]).json()
    encerrar(api, encerrada["id"])

    criadas = {ativa["id"], encerrada["id"]}

    def ids(**parametros):
        # Considera só as matrículas deste teste: o banco pode ter outras, criadas à mão
        lista = api.get("/api/matriculas", params=parametros).json()
        return [m["id"] for m in lista if m["id"] in criadas]

    assert ids() == [ativa["id"]]
    assert ids(situacao="encerradas") == [encerrada["id"]]
    assert sorted(ids(situacao="todas")) == sorted([ativa["id"], encerrada["id"]])
    assert ids(situacao="todas", busca="laura") == [encerrada["id"]]
    assert ids(situacao="todas", aluno_id=aluno["id"]) == [ativa["id"]]


def test_matricula_inexistente(api):
    assert api.get("/api/matriculas/999999").status_code == 404
    assert encerrar(api, 999999).status_code == 404


# ---------- Integridade e concorrência ----------


def test_banco_nao_aceita_duas_matriculas_ativas(db, aluno):
    dados = {"aluno_id": aluno["id"], "data_inicio": date(2026, 1, 15), "valor_mensalidade": 10}
    db.add(Matricula(**dados))
    db.flush()
    db.add(Matricula(**dados))
    with pytest.raises(IntegrityError):
        db.flush()


def test_duas_requisicoes_ao_mesmo_tempo_nao_viram_erro_500(api, aluno, monkeypatch):
    primeira = matricular(api, aluno["id"]).json()
    # Simula a corrida: a checagem não enxerga a matrícula criada pela outra requisição
    monkeypatch.setattr(rota_matriculas, "tem_matricula_ativa", lambda db, aluno_id: False)

    assert matricular(api, aluno["id"]).status_code == 409

    ativas = api.get("/api/matriculas", params={"aluno_id": aluno["id"]}).json()
    assert [m["id"] for m in ativas] == [primeira["id"]]


# ---------- Entradas fora do normal (nunca pode dar erro 500) ----------

ID_GIGANTE = 99999999999999


@pytest.mark.parametrize("id_ruim", [0, -1, ID_GIGANTE])
def test_ids_invalidos_viram_422(api, id_ruim):
    assert api.get(f"/api/matriculas/{id_ruim}").status_code == 422
    assert encerrar(api, id_ruim).status_code == 422
    assert api.get("/api/matriculas", params={"aluno_id": id_ruim}).status_code == 422
    assert matricular(api, id_ruim).status_code == 422


def test_id_que_nao_e_numero_vira_422(api):
    assert api.get("/api/matriculas/abc").status_code == 422
    assert api.get("/api/matriculas", params={"aluno_id": "abc"}).status_code == 422


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("0.01", "0.01"),
        ("99999999.99", "99999999.99"),
        ("1e5", "100000.00"),
        (150, "150.00"),
        (89.9, "89.90"),
        ("  120,5  ", "120.50"),
    ],
)
def test_valores_extremos_aceitos(api, aluno, valor, esperado):
    resposta = matricular(api, aluno["id"], valor_mensalidade=valor)
    assert resposta.status_code == 201
    assert resposta.json()["valor_mensalidade"] == esperado


@pytest.mark.parametrize(
    "valor",
    ["0.001", "1e999999999", "9" * 500, "NaN", "Infinity", "-Infinity", True, [], {}, "R$ 10"],
)
def test_valores_estranhos_rejeitados(api, aluno, valor):
    assert matricular(api, aluno["id"], valor_mensalidade=valor).status_code == 422


@pytest.mark.parametrize("data", ["0001-01-01", "9999-12-31", "2026-02-30", "ontem", 20260115, []])
def test_datas_estranhas_nunca_dao_erro_500(api, aluno, data):
    assert matricular(api, aluno["id"], data_inicio=data).status_code < 500


@pytest.mark.parametrize("data", ["0001-01-01", "9999-12-31", "2026-02-30", "ontem", 0, []])
def test_encerramento_com_data_estranha_nunca_da_erro_500(api, aluno, data):
    matricula = matricular(api, aluno["id"]).json()
    assert encerrar(api, matricula["id"], data_encerramento=data).status_code < 500


def test_corpo_que_nao_e_json_vira_422(api):
    cabecalho = {"Content-Type": "application/json"}
    assert api.post("/api/matriculas", content=b"{", headers=cabecalho).status_code == 422
    assert api.post("/api/matriculas", content=b"[]", headers=cabecalho).status_code == 422
    assert api.post("/api/matriculas").status_code == 422


def test_encerra_no_proprio_dia_do_inicio(api, aluno):
    hoje = date.today().isoformat()
    matricula = matricular(api, aluno["id"], data_inicio=hoje).json()
    assert encerrar(api, matricula["id"], data_encerramento=hoje).status_code == 200


# ---------- Segurança ----------


def test_campos_de_controle_enviados_pelo_cliente_sao_ignorados(api, aluno):
    extras = {"situacao": "encerrada", "data_encerramento": "2026-01-20", "id": 424242}
    matricula = matricular(api, aluno["id"], **extras).json()
    assert matricula["situacao"] == "ativa"
    assert matricula["data_encerramento"] is None
    assert matricula["id"] != 424242

    encerrada = encerrar(api, matricula["id"], situacao="ativa", valor_mensalidade="1.00").json()
    assert encerrada["situacao"] == "encerrada"
    assert encerrada["valor_mensalidade"] == "150.00"


def test_matricula_nao_pode_ser_apagada_nem_editada(api, aluno):
    matricula = matricular(api, aluno["id"]).json()
    url = f"/api/matriculas/{matricula['id']}"
    assert api.delete(url).status_code == 405
    assert api.put(url, json={}).status_code == 405
    assert api.patch(url, json={}).status_code == 405
    assert api.get(url).status_code == 200


def test_resposta_nao_expoe_contatos_dos_responsaveis(api, aluno):
    matricula = matricular(api, aluno["id"]).json()
    assert set(matricula) == {
        "id",
        "aluno",
        "data_inicio",
        "data_encerramento",
        "valor_mensalidade",
        "bolsa",
        "situacao",
    }
    assert set(matricula["aluno"]) == {"id", "nome", "ativo"}
    assert "31988887777" not in api.get("/api/matriculas").text


@pytest.mark.parametrize(
    "busca",
    ["'; DROP TABLE matriculas; --", "' OR '1'='1", '" OR ""="', "\\", "%", "_", "a" * 10000],
)
def test_busca_nao_e_vulneravel_a_injecao_de_sql(api, db, aluno, busca):
    matricular(api, aluno["id"])
    total = db.scalar(select(func.count()).select_from(Matricula))
    resposta = api.get("/api/matriculas", params={"busca": busca, "situacao": "todas"})
    assert resposta.status_code == 200
    assert resposta.json() == []
    assert db.scalar(select(func.count()).select_from(Matricula)) == total


# ---------- Listagem ----------


def test_situacao_invalida_na_listagem(api):
    assert api.get("/api/matriculas", params={"situacao": "xyz"}).status_code == 422


def test_lista_em_ordem_de_aluno_e_depois_da_mais_recente(api, aluno):
    responsavel_id = aluno["responsaveis"][0]["id"]
    ana = api.post("/api/alunos", json={"nome": "Ana Lima", "responsavel_ids": [responsavel_id]})
    antiga = matricular(api, ana.json()["id"], data_inicio="2026-01-10").json()
    encerrar(api, antiga["id"], data_encerramento="2026-02-01")
    recente = matricular(api, ana.json()["id"], data_inicio="2026-03-01").json()
    zeca = api.post("/api/alunos", json={"nome": "Zeca Reis", "responsavel_ids": [responsavel_id]})
    ultima = matricular(api, zeca.json()["id"]).json()
    pedro = matricular(api, aluno["id"]).json()

    esperada = [recente["id"], antiga["id"], pedro["id"], ultima["id"]]
    lista = api.get("/api/matriculas", params={"situacao": "todas"}).json()
    # Considera só as matrículas deste teste: o banco pode ter outras, criadas à mão
    assert [m["id"] for m in lista if m["id"] in esperada] == esperada


def test_busca_com_caractere_nulo_nao_da_erro_500(api, aluno):
    matricular(api, aluno["id"])
    resposta = api.get("/api/matriculas", params={"busca": "Pedro\x00 Souza"})
    assert resposta.status_code == 200
    assert [m["aluno"]["nome"] for m in resposta.json()] == ["Pedro Souza"]


def test_busca_ignora_maiusculas_e_acentos_de_espaco(api, aluno):
    matricular(api, aluno["id"])
    for busca in ["pedro", "PEDRO", "  souza  ", "ro sou"]:
        resposta = api.get("/api/matriculas", params={"busca": busca})
        assert [m["aluno"]["nome"] for m in resposta.json()] == ["Pedro Souza"], busca
