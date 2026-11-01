from datetime import date

import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.exc import DataError, IntegrityError

from app.core import tempo
from app.db.session import engine
from app.models import Matricula, Perfil

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


def matricular(cliente, aluno_id, **campos):
    corpo = {"aluno_id": aluno_id, "data_inicio": "2026-01-15", "valor_mensalidade": "150.00"}
    return cliente.post("/api/matriculas", json=corpo | campos)


def apadrinhar(cliente, aluno, padrinho, **campos) -> dict:
    resposta = matricular(
        cliente, aluno["id"], bolsa="apadrinhada", padrinho_id=padrinho["id"], **campos
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


def gerar(cliente, mes="2026-11") -> dict:
    resposta = cliente.post("/api/mensalidades/gerar", json={"competencia": mes})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def da_matricula(db, matricula_id) -> Matricula:
    db.expire_all()
    return db.get(Matricula, matricula_id)


# ---------- Matricular um aluno apadrinhado ----------


def test_matricula_apadrinhada_guarda_a_empresa_e_mantem_o_valor(api, db, novo_aluno):
    aluno = novo_aluno("Pedro Souza")
    padrinho = novo_padrinho(api)

    resposta = matricular(
        api,
        aluno["id"],
        bolsa="apadrinhada",
        padrinho_id=padrinho["id"],
        valor_mensalidade="150.00",
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["bolsa"] == "apadrinhada"
    assert corpo["valor_mensalidade"] == "150.00"  # o valor não é zero: a empresa paga 100% dele
    assert corpo["padrinho"] == {"id": padrinho["id"], "nome": "Sartori Serviços", "ativo": True}
    assert corpo["situacao"] == "ativa"
    no_banco = da_matricula(db, corpo["id"])
    assert no_banco.padrinho_id == padrinho["id"]
    assert str(no_banco.valor_mensalidade) == "150.00"


def test_a_consulta_e_a_lista_trazem_a_empresa(api, novo_aluno):
    padrinho = novo_padrinho(api)
    criada = apadrinhar(api, novo_aluno("Pedro Souza"), padrinho)

    de_um = api.get(f"/api/matriculas/{criada['id']}").json()
    da_lista = api.get("/api/matriculas").json()[0]

    assert de_um["padrinho"] == da_lista["padrinho"] == criada["padrinho"]


def test_a_resposta_traz_so_nome_da_empresa_e_nao_os_contatos(api, novo_aluno):
    padrinho = novo_padrinho(api, cnpj="11222333000181", contato="Marcos")
    criada = apadrinhar(api, novo_aluno(), padrinho)

    assert set(criada["padrinho"]) == {"id", "nome", "ativo"}
    texto = api.get("/api/matriculas").text
    for segredo in ("11222333000181", "98888-7777", "financeiro@sartori", "Marcos"):
        assert segredo not in texto


def test_aceita_o_valor_com_virgula(api, novo_aluno):
    padrinho = novo_padrinho(api)
    resposta = matricular(
        api,
        novo_aluno()["id"],
        bolsa="apadrinhada",
        padrinho_id=padrinho["id"],
        valor_mensalidade="89,90",
    )
    assert resposta.json()["valor_mensalidade"] == "89.90"


@pytest.mark.parametrize("valor", [None, "", "0", "0,00", "-5", "abc", "NaN", "100000000"])
def test_a_empresa_paga_um_valor_de_verdade_nunca_zero_nem_vazio(api, novo_aluno, valor):
    padrinho = novo_padrinho(api)
    resposta = matricular(
        api,
        novo_aluno()["id"],
        bolsa="apadrinhada",
        padrinho_id=padrinho["id"],
        valor_mensalidade=valor,
    )
    assert "valor_mensalidade" in erros_de(resposta)


def test_um_padrinho_pode_apadrinhar_varios_alunos(api, novo_aluno):
    padrinho = novo_padrinho(api)
    for nome in ("Pedro Souza", "Laura Souza", "Lucas Ferreira"):
        apadrinhar(api, novo_aluno(nome), padrinho, valor_mensalidade="150.00")

    lista = api.get("/api/matriculas").json()
    assert {m["padrinho"]["id"] for m in lista} == {padrinho["id"]}
    assert len(lista) == 3


def test_cada_aluno_pode_ter_valor_diferente_para_a_mesma_empresa(api, novo_aluno):
    padrinho = novo_padrinho(api)
    apadrinhar(api, novo_aluno("Ana"), padrinho, valor_mensalidade="150.00")
    apadrinhar(api, novo_aluno("Beto"), padrinho, valor_mensalidade="120.50")
    valores = {
        m["aluno"]["nome"]: m["valor_mensalidade"] for m in api.get("/api/matriculas").json()
    }
    assert valores == {"Ana": "150.00", "Beto": "120.50"}


# ---------- A empresa é obrigatória na apadrinhada e proibida nas outras ----------


@pytest.mark.parametrize("padrinho_id", [None, "missing"])
def test_apadrinhada_exige_escolher_a_empresa(api, db, novo_aluno, padrinho_id):
    corpo = {
        "aluno_id": novo_aluno()["id"],
        "data_inicio": "2026-01-15",
        "valor_mensalidade": "150.00",
        "bolsa": "apadrinhada",
    }
    if padrinho_id != "missing":
        corpo["padrinho_id"] = padrinho_id
    erros = erros_de(api.post("/api/matriculas", json=corpo))
    assert erros["padrinho_id"] == "Escolha a empresa que apadrinha o aluno"
    assert db.scalars(select(Matricula)).all() == []


@pytest.mark.parametrize("bolsa", ["nenhuma", "parcial", "integral"])
def test_as_outras_bolsas_nao_tem_empresa(api, db, novo_aluno, bolsa):
    padrinho = novo_padrinho(api)
    valor = "0" if bolsa == "integral" else "150.00"
    resposta = matricular(
        api, novo_aluno()["id"], bolsa=bolsa, padrinho_id=padrinho["id"], valor_mensalidade=valor
    )
    assert erros_de(resposta)["padrinho_id"] == "Só a bolsa apadrinhada tem empresa"
    assert db.scalars(select(Matricula)).all() == []


@pytest.mark.parametrize("bolsa", ["nenhuma", "parcial", "integral"])
def test_as_outras_bolsas_continuam_sem_empresa(api, novo_aluno, bolsa):
    valor = "" if bolsa == "integral" else "150.00"
    resposta = matricular(api, novo_aluno()["id"], bolsa=bolsa, valor_mensalidade=valor)
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["padrinho"] is None


def test_padrinho_nulo_nas_outras_bolsas_e_aceito(api, novo_aluno):
    resposta = matricular(api, novo_aluno()["id"], padrinho_id=None)
    assert resposta.status_code == 201
    assert resposta.json()["padrinho"] is None


# ---------- A empresa precisa existir e estar ativa ----------


def test_empresa_inexistente_da_422(api, db, novo_aluno):
    resposta = matricular(api, novo_aluno()["id"], bolsa="apadrinhada", padrinho_id=999999)
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Padrinho não encontrado"
    assert db.scalars(select(Matricula)).all() == []


@pytest.mark.parametrize(
    "padrinho_id", [0, -1, 2_147_483_648, 99999999999999999999, "abc", 1.5, True, [1], {}]
)
def test_empresa_com_id_fora_do_normal_da_422_e_nao_500(api, novo_aluno, padrinho_id):
    resposta = matricular(api, novo_aluno()["id"], bolsa="apadrinhada", padrinho_id=padrinho_id)
    assert resposta.status_code == 422
    assert "padrinho_id" in erros_de(resposta)


def test_so_empresa_ativa_pode_apadrinhar(api, db, novo_aluno):
    padrinho = novo_padrinho(api)
    corpo = {
        "nome": padrinho["nome"],
        "telefone": "31988887777",
        "email": "a@b.com",
        "dia_vencimento": 25,
        "ativo": False,
    }
    api.put(f"/api/padrinhos/{padrinho['id']}", json=corpo)

    resposta = matricular(api, novo_aluno()["id"], bolsa="apadrinhada", padrinho_id=padrinho["id"])

    assert resposta.status_code == 422
    assert (
        resposta.json()["detail"]
        == "Padrinho inativo não pode apadrinhar. Reative o padrinho antes."
    )
    assert db.scalars(select(Matricula)).all() == []


def test_reativar_a_empresa_libera_o_apadrinhamento(api, novo_aluno):
    padrinho = novo_padrinho(api)
    base = {
        "nome": padrinho["nome"],
        "telefone": "31988887777",
        "email": "a@b.com",
        "dia_vencimento": 25,
    }
    api.put(f"/api/padrinhos/{padrinho['id']}", json=base | {"ativo": False})
    aluno = novo_aluno()
    assert (
        matricular(api, aluno["id"], bolsa="apadrinhada", padrinho_id=padrinho["id"]).status_code
        == 422
    )

    api.put(f"/api/padrinhos/{padrinho['id']}", json=base | {"ativo": True})

    assert (
        matricular(api, aluno["id"], bolsa="apadrinhada", padrinho_id=padrinho["id"]).status_code
        == 201
    )


def test_inativar_a_empresa_depois_nao_mexe_na_matricula_que_ja_existe(api, novo_aluno):
    padrinho = novo_padrinho(api)
    criada = apadrinhar(api, novo_aluno(), padrinho)
    base = {
        "nome": padrinho["nome"],
        "telefone": "31988887777",
        "email": "a@b.com",
        "dia_vencimento": 25,
    }

    api.put(f"/api/padrinhos/{padrinho['id']}", json=base | {"ativo": False})

    depois = api.get(f"/api/matriculas/{criada['id']}").json()
    assert depois["situacao"] == "ativa"
    assert depois["bolsa"] == "apadrinhada"
    assert depois["padrinho"] == {"id": padrinho["id"], "nome": "Sartori Serviços", "ativo": False}


# ---------- Um aluno, uma empresa por vez (RN17) ----------


def test_aluno_apadrinhado_nao_pode_ter_outra_matricula_ativa_com_outra_empresa(api, novo_aluno):
    primeira, segunda = novo_padrinho(api, "Primeira Ltda"), novo_padrinho(api, "Segunda Ltda")
    aluno = novo_aluno()
    criada = apadrinhar(api, aluno, primeira)

    resposta = matricular(api, aluno["id"], bolsa="apadrinhada", padrinho_id=segunda["id"])

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Este aluno já tem uma matrícula ativa"
    assert api.get(f"/api/matriculas/{criada['id']}").json()["padrinho"]["nome"] == "Primeira Ltda"


def test_trocar_de_empresa_encerra_e_matricula_de_novo_sem_perder_o_historico(api, novo_aluno):
    primeira, segunda = novo_padrinho(api, "Primeira Ltda"), novo_padrinho(api, "Segunda Ltda")
    aluno = novo_aluno("Pedro Souza")
    antiga = apadrinhar(api, aluno, primeira)
    api.patch(f"/api/matriculas/{antiga['id']}/encerrar", json={"data_encerramento": "2026-06-30"})

    nova = matricular(
        api,
        aluno["id"],
        bolsa="apadrinhada",
        padrinho_id=segunda["id"],
        data_inicio="2026-07-01",
        valor_mensalidade="180.00",
    )

    assert nova.status_code == 201
    historico = api.get("/api/matriculas", params={"situacao": "todas"}).json()
    por_empresa = {m["padrinho"]["nome"]: m for m in historico}
    assert por_empresa["Primeira Ltda"]["situacao"] == "encerrada"
    assert por_empresa["Primeira Ltda"]["data_encerramento"] == "2026-06-30"
    assert por_empresa["Segunda Ltda"]["situacao"] == "ativa"
    assert por_empresa["Segunda Ltda"]["valor_mensalidade"] == "180.00"


def test_voltar_a_pagar_encerra_e_matricula_sem_bolsa(api, novo_aluno):
    padrinho = novo_padrinho(api)
    aluno = novo_aluno()
    antiga = apadrinhar(api, aluno, padrinho)
    api.patch(f"/api/matriculas/{antiga['id']}/encerrar", json={"data_encerramento": "2026-06-30"})

    nova = matricular(api, aluno["id"], data_inicio="2026-07-01", valor_mensalidade="150.00")

    assert nova.status_code == 201
    assert nova.json()["bolsa"] == "nenhuma"
    assert nova.json()["padrinho"] is None
    historico = api.get("/api/matriculas", params={"situacao": "todas"}).json()
    assert sorted(m["bolsa"] for m in historico) == ["apadrinhada", "nenhuma"]


def test_encerrar_a_matricula_apadrinhada_nao_apaga_a_empresa_do_historico(api, novo_aluno):
    padrinho = novo_padrinho(api)
    criada = apadrinhar(api, novo_aluno(), padrinho)
    encerrada = api.patch(
        f"/api/matriculas/{criada['id']}/encerrar", json={"data_encerramento": "2026-10-31"}
    ).json()
    assert encerrada["situacao"] == "encerrada"
    assert encerrada["padrinho"]["id"] == padrinho["id"]


def test_inativar_o_aluno_encerra_a_matricula_apadrinhada(api, novo_aluno):
    padrinho = novo_padrinho(api)
    aluno = novo_aluno("Pedro Souza")
    criada = apadrinhar(api, aluno, padrinho)
    atual = api.get(f"/api/alunos/{aluno['id']}").json()
    corpo = {
        "nome": atual["nome"],
        "responsavel_ids": [r["id"] for r in atual["responsaveis"]],
        "ativo": False,
    }

    assert api.put(f"/api/alunos/{aluno['id']}", json=corpo).status_code == 200

    depois = api.get(f"/api/matriculas/{criada['id']}").json()
    assert depois["situacao"] == "encerrada"
    assert depois["padrinho"]["id"] == padrinho["id"]


def test_aluno_inativo_nao_pode_ser_apadrinhado(api, novo_aluno):
    padrinho = novo_padrinho(api)
    aluno = novo_aluno()
    atual = api.get(f"/api/alunos/{aluno['id']}").json()
    api.put(
        f"/api/alunos/{aluno['id']}",
        json={
            "nome": atual["nome"],
            "responsavel_ids": [r["id"] for r in atual["responsaveis"]],
            "ativo": False,
        },
    )
    resposta = matricular(api, aluno["id"], bolsa="apadrinhada", padrinho_id=padrinho["id"])
    assert resposta.status_code == 422


def test_campos_extras_sao_ignorados(api, novo_aluno):
    padrinho = novo_padrinho(api)
    resposta = matricular(
        api,
        novo_aluno()["id"],
        bolsa="apadrinhada",
        padrinho_id=padrinho["id"],
        padrinho={"id": 999, "nome": "Invasor", "ativo": True},
        situacao="encerrada",
        id=77,
    )
    assert resposta.status_code == 201
    assert resposta.json()["padrinho"]["id"] == padrinho["id"]
    assert resposta.json()["situacao"] == "ativa"


# ---------- Permissões (RN13) ----------


def test_sem_login_nao_matricula(sem_login):
    assert sem_login.post("/api/matriculas", json={}).status_code == 401


def test_consulta_nao_apadrinha(api, api_como, db, novo_aluno):
    padrinho = novo_padrinho(api)
    aluno = novo_aluno()

    resposta = matricular(
        api_como(Perfil.CONSULTA), aluno["id"], bolsa="apadrinhada", padrinho_id=padrinho["id"]
    )

    assert resposta.status_code == 403
    assert db.scalars(select(Matricula)).all() == []


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.ADMINISTRADOR])
def test_operador_e_administrador_apadrinham(api, api_como, novo_aluno, perfil):
    padrinho = novo_padrinho(api)
    cliente = api_como(perfil)
    resposta = matricular(
        cliente, novo_aluno()["id"], bolsa="apadrinhada", padrinho_id=padrinho["id"]
    )
    assert resposta.status_code == 201


def test_o_perfil_e_conferido_antes_da_empresa(api_como):
    """A consulta não descobre se a empresa existe."""
    resposta = api_como(Perfil.CONSULTA).post(
        "/api/matriculas",
        json={
            "aluno_id": 1,
            "data_inicio": "2026-01-15",
            "bolsa": "apadrinhada",
            "padrinho_id": 999999,
        },
    )
    assert resposta.status_code == 403


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_veem_a_empresa_na_lista(api, api_como, novo_aluno, perfil):
    padrinho = novo_padrinho(api)
    apadrinhar(api, novo_aluno(), padrinho)
    (matricula,) = api_como(perfil).get("/api/matriculas").json()
    assert matricula["padrinho"]["nome"] == "Sartori Serviços"


# ---------- Listar, filtrar por empresa e buscar ----------


def test_filtra_as_matriculas_por_empresa(api, novo_aluno):
    a, b = novo_padrinho(api, "Alfa Ltda"), novo_padrinho(api, "Beta Ltda")
    apadrinhar(api, novo_aluno("Ana"), a)
    apadrinhar(api, novo_aluno("Beto"), b)
    apadrinhar(api, novo_aluno("Carla"), a)
    matricular(api, novo_aluno("Davi")["id"])

    def nomes(**parametros):
        return [m["aluno"]["nome"] for m in api.get("/api/matriculas", params=parametros).json()]

    assert nomes(padrinho_id=a["id"]) == ["Ana", "Carla"]
    assert nomes(padrinho_id=b["id"]) == ["Beto"]
    assert nomes() == ["Ana", "Beto", "Carla", "Davi"]


def test_filtro_de_empresa_sem_alunos_devolve_lista_vazia(api):
    padrinho = novo_padrinho(api)
    assert api.get("/api/matriculas", params={"padrinho_id": padrinho["id"]}).json() == []
    assert api.get("/api/matriculas", params={"padrinho_id": 999999}).json() == []


@pytest.mark.parametrize("valor", [0, -1, 2_147_483_648, "abc", 1.5])
def test_filtro_de_empresa_invalido_da_422(api, valor):
    assert api.get("/api/matriculas", params={"padrinho_id": valor}).status_code == 422


def test_filtro_de_empresa_combina_com_a_situacao(api, novo_aluno):
    padrinho = novo_padrinho(api)
    antiga = apadrinhar(api, novo_aluno("Ana"), padrinho)
    apadrinhar(api, novo_aluno("Beto"), padrinho)
    api.patch(f"/api/matriculas/{antiga['id']}/encerrar", json={"data_encerramento": "2026-06-30"})

    def nomes(situacao):
        resposta = api.get(
            "/api/matriculas", params={"padrinho_id": padrinho["id"], "situacao": situacao}
        )
        return [m["aluno"]["nome"] for m in resposta.json()]

    assert nomes("ativas") == ["Beto"]
    assert nomes("encerradas") == ["Ana"]
    assert nomes("todas") == ["Ana", "Beto"]


def test_a_busca_tambem_procura_no_nome_da_empresa(api, novo_aluno):
    sartori = novo_padrinho(api, "Sartori Serviços")
    outra = novo_padrinho(api, "Outra Empresa")
    apadrinhar(api, novo_aluno("Pedro Souza"), sartori)
    apadrinhar(api, novo_aluno("Laura Lima"), outra)
    matricular(api, novo_aluno("Marta Sartori Lima")["id"])

    def nomes(busca):
        return [
            m["aluno"]["nome"] for m in api.get("/api/matriculas", params={"busca": busca}).json()
        ]

    assert nomes("sartori") == ["Marta Sartori Lima", "Pedro Souza"]  # pela empresa e pelo aluno
    assert nomes("OUTRA") == ["Laura Lima"]
    assert nomes("pedro") == ["Pedro Souza"]
    assert nomes("inexistente") == []


def test_busca_com_curingas_e_caractere_nulo_nao_quebra(api, novo_aluno):
    padrinho = novo_padrinho(api, "Empresa 100% Boa")
    apadrinhar(api, novo_aluno("Pedro"), padrinho)
    matricular(api, novo_aluno("Outro")["id"])

    def nomes(busca):
        return [
            m["aluno"]["nome"] for m in api.get("/api/matriculas", params={"busca": busca}).json()
        ]

    assert nomes("%") == ["Pedro"]
    assert nomes("100%") == ["Pedro"]
    assert nomes("_") == []
    assert len(nomes(chr(0))) == 2
    assert len(nomes("a" + chr(0) + "b")) == 0


def test_matriculas_sem_empresa_continuam_na_lista(api, novo_aluno):
    """A junção com a empresa não pode esconder quem não tem empresa."""
    padrinho = novo_padrinho(api)
    apadrinhar(api, novo_aluno("Com Empresa"), padrinho)
    matricular(api, novo_aluno("Sem Empresa")["id"])
    matricular(api, novo_aluno("Bolsista")["id"], bolsa="parcial", valor_mensalidade="80.00")
    assert [m["aluno"]["nome"] for m in api.get("/api/matriculas").json()] == [
        "Bolsista",
        "Com Empresa",
        "Sem Empresa",
    ]


def test_so_bolsistas_inclui_o_apadrinhado(api, novo_aluno):
    padrinho = novo_padrinho(api)
    apadrinhar(api, novo_aluno("Apadrinhado"), padrinho)
    matricular(api, novo_aluno("Integral")["id"], bolsa="integral", valor_mensalidade="")
    matricular(api, novo_aluno("Paga Tudo")["id"])
    nomes = [
        m["aluno"]["nome"]
        for m in api.get("/api/matriculas", params={"so_bolsistas": "true"}).json()
    ]
    assert nomes == ["Apadrinhado", "Integral"]


def contar_consultas(cliente, db) -> int:
    db.expire_all()  # esquece o que a sessão de teste já tem, para uma consulta por linha aparecer
    total = 0

    def conta(*_):
        nonlocal total
        total += 1

    event.listen(engine, "before_cursor_execute", conta)
    try:
        assert cliente.get("/api/matriculas").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", conta)
    return total


def test_a_lista_nao_faz_uma_consulta_por_matricula(api, db, novo_aluno):
    for i in range(2):
        apadrinhar(api, novo_aluno(f"Aluno {i}"), novo_padrinho(api, f"Empresa {i}"))
    com_2 = contar_consultas(api, db)

    for i in range(2, 9):
        apadrinhar(api, novo_aluno(f"Aluno {i}"), novo_padrinho(api, f"Empresa {i}"))
    com_9 = contar_consultas(api, db)

    assert len(api.get("/api/matriculas").json()) == 9
    assert com_9 == com_2


# ---------- Geração das mensalidades: o responsável não é cobrado (RN16) ----------


def test_a_matricula_apadrinhada_nao_gera_mensalidade_para_o_responsavel(api, novo_aluno):
    padrinho = novo_padrinho(api)
    apadrinhar(api, novo_aluno("Apadrinhado"), padrinho)

    resultado = gerar(api)

    assert resultado == {
        "competencia": "2026-11-01",
        "geradas": 0,
        "ja_existiam": 0,
        "bolsa_integral": 0,
        "apadrinhados": 1,
        "apadrinhados_incluidos": 1,
        "cobrancas_criadas": 1,
        "ainda_nao_comecaram": 0,
    }
    # A mensalidade dele existe, mas na cobrança da empresa: não aparece para o responsável
    assert api.get("/api/mensalidades").json() == []


def test_na_mesma_geracao_so_quem_paga_pelo_responsavel_e_cobrado(api, novo_aluno):
    padrinho = novo_padrinho(api)
    apadrinhar(api, novo_aluno("Apadrinhado Um"), padrinho)
    apadrinhar(api, novo_aluno("Apadrinhado Dois"), padrinho)
    matricular(api, novo_aluno("Paga Tudo")["id"])
    matricular(api, novo_aluno("Parcial")["id"], bolsa="parcial", valor_mensalidade="80.00")
    matricular(api, novo_aluno("Integral")["id"], bolsa="integral", valor_mensalidade="")

    resultado = gerar(api)

    assert (resultado["geradas"], resultado["bolsa_integral"], resultado["apadrinhados"]) == (
        2,
        1,
        2,
    )
    nomes = sorted(m["aluno"]["nome"] for m in api.get("/api/mensalidades").json())
    assert nomes == ["Paga Tudo", "Parcial"]


def test_gerar_de_novo_nao_muda_nada_para_o_apadrinhado(api, novo_aluno):
    apadrinhar(api, novo_aluno(), novo_padrinho(api))
    primeiro, segundo = gerar(api), gerar(api)
    assert (primeiro["apadrinhados_incluidos"], primeiro["cobrancas_criadas"]) == (1, 1)
    # Na segunda vez ele continua apadrinhado, mas já estava na cobrança: nada entra de novo
    assert (segundo["apadrinhados"], segundo["apadrinhados_incluidos"]) == (1, 0)
    assert segundo["cobrancas_criadas"] == 0
    assert api.get("/api/mensalidades").json() == []


def test_apadrinhado_nao_aparece_nas_pendencias_do_responsavel(api, monkeypatch, novo_aluno):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 12, 20))
    apadrinhar(api, novo_aluno("Apadrinhado"), novo_padrinho(api))
    matricular(api, novo_aluno("Devedor")["id"])
    gerar(api, "2026-11")

    painel = api.get("/api/pendencias").json()

    nomes = [a["nome"] for g in painel["grupos"] for a in g["alunos"]]
    assert nomes == ["Devedor"]
    assert painel["resumo"]["total_em_aberto"] == "150.00"


def test_apadrinhada_que_ainda_nao_comecou_nao_conta_como_ainda_nao_comecou(api, novo_aluno):
    """Quem paga pelo responsável e começa depois do mês entra nesse contador; o apadrinhado não."""
    apadrinhar(api, novo_aluno("Futuro Apadrinhado"), novo_padrinho(api), data_inicio="2027-03-01")
    matricular(api, novo_aluno("Futuro Normal")["id"], data_inicio="2027-03-01")

    resultado = gerar(api)

    assert resultado["ainda_nao_comecaram"] == 1
    assert resultado["apadrinhados"] == 0  # ainda não está em vigor neste mês


def test_apadrinhada_encerrada_no_meio_do_mes_ainda_conta_nesse_mes(api, novo_aluno):
    padrinho = novo_padrinho(api)
    criada = apadrinhar(api, novo_aluno(), padrinho, data_inicio="2026-01-15")
    api.patch(f"/api/matriculas/{criada['id']}/encerrar", json={"data_encerramento": "2026-10-20"})
    assert gerar(api, "2026-10")["apadrinhados"] == 1
    assert gerar(api, "2026-11")["apadrinhados"] == 0


def test_quem_era_apadrinhado_e_volta_a_pagar_e_cobrado_a_partir_da_nova_matricula(api, novo_aluno):
    padrinho = novo_padrinho(api)
    aluno = novo_aluno("Pedro")
    antiga = apadrinhar(api, aluno, padrinho, data_inicio="2026-01-15")
    api.patch(f"/api/matriculas/{antiga['id']}/encerrar", json={"data_encerramento": "2026-10-31"})
    matricular(api, aluno["id"], data_inicio="2026-11-01", valor_mensalidade="150.00")

    assert gerar(api, "2026-10")["apadrinhados"] == 1
    novembro = gerar(api, "2026-11")

    assert (novembro["geradas"], novembro["apadrinhados"]) == (1, 0)
    assert [m["competencia"] for m in api.get("/api/mensalidades").json()] == ["2026-11-01"]


def test_aluno_que_virou_apadrinhado_no_mes_nao_e_cobrado_em_dobro(api, novo_aluno):
    """Pagava pelo responsável até 14/10 e foi apadrinhado: a última matrícula do mês vale."""
    padrinho = novo_padrinho(api)
    aluno = novo_aluno("Pedro")
    antiga = matricular(api, aluno["id"], data_inicio="2026-01-15").json()
    api.patch(f"/api/matriculas/{antiga['id']}/encerrar", json={"data_encerramento": "2026-10-14"})
    apadrinhar(api, aluno, padrinho, data_inicio="2026-10-15")

    resultado = gerar(api, "2026-10")

    assert (resultado["geradas"], resultado["apadrinhados"]) == (0, 1)
    assert api.get("/api/mensalidades").json() == []


def test_mensalidade_ja_gerada_antes_do_apadrinhamento_continua_com_o_responsavel(api, novo_aluno):
    padrinho = novo_padrinho(api)
    aluno = novo_aluno("Pedro")
    antiga = matricular(api, aluno["id"], data_inicio="2026-01-15").json()
    assert gerar(api, "2026-10")["geradas"] == 1
    api.patch(f"/api/matriculas/{antiga['id']}/encerrar", json={"data_encerramento": "2026-10-31"})
    apadrinhar(api, aluno, padrinho, data_inicio="2026-11-01")

    gerar(api, "2026-11")

    meses = [m["competencia"] for m in api.get("/api/mensalidades").json()]
    assert meses == ["2026-10-01"]  # a de outubro continua; a de novembro é da empresa


# ---------- Quantos alunos a empresa apadrinha ----------


def test_a_empresa_informa_quantos_alunos_apadrinha(api, novo_aluno):
    a, b = novo_padrinho(api, "Alfa Ltda"), novo_padrinho(api, "Beta Ltda")
    sem = novo_padrinho(api, "Sem Alunos Ltda")
    apadrinhar(api, novo_aluno("Ana"), a)
    apadrinhar(api, novo_aluno("Beto"), a)
    apadrinhar(api, novo_aluno("Carla"), b)

    lista = {p["nome"]: p["alunos_apadrinhados"] for p in api.get("/api/padrinhos").json()}
    assert lista == {"Alfa Ltda": 2, "Beta Ltda": 1, "Sem Alunos Ltda": 0}
    assert api.get(f"/api/padrinhos/{a['id']}").json()["alunos_apadrinhados"] == 2
    assert api.get(f"/api/padrinhos/{sem['id']}").json()["alunos_apadrinhados"] == 0


def test_so_a_matricula_ativa_conta_para_a_empresa(api, novo_aluno):
    padrinho = novo_padrinho(api)
    encerrada = apadrinhar(api, novo_aluno("Ana"), padrinho)
    apadrinhar(api, novo_aluno("Beto"), padrinho)
    matricular(api, novo_aluno("Sem Empresa")["id"])

    assert api.get(f"/api/padrinhos/{padrinho['id']}").json()["alunos_apadrinhados"] == 2
    api.patch(
        f"/api/matriculas/{encerrada['id']}/encerrar", json={"data_encerramento": "2026-10-31"}
    )
    assert api.get(f"/api/padrinhos/{padrinho['id']}").json()["alunos_apadrinhados"] == 1


def test_a_contagem_vem_tambem_no_cadastro_e_na_edicao(api, novo_aluno):
    padrinho = novo_padrinho(api)
    assert padrinho["alunos_apadrinhados"] == 0
    apadrinhar(api, novo_aluno(), padrinho)
    base = {
        "nome": padrinho["nome"],
        "telefone": "31988887777",
        "email": "a@b.com",
        "dia_vencimento": 25,
    }

    inativado = api.put(f"/api/padrinhos/{padrinho['id']}", json=base | {"ativo": False}).json()

    assert inativado["alunos_apadrinhados"] == 1  # inativar não encerra as matrículas
    assert inativado["ativo"] is False


def test_a_lista_de_padrinhos_nao_faz_uma_consulta_por_empresa(api, db, novo_aluno):
    def contar():
        db.expire_all()
        total = 0

        def conta(*_):
            nonlocal total
            total += 1

        event.listen(engine, "before_cursor_execute", conta)
        try:
            assert api.get("/api/padrinhos").status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", conta)
        return total

    for i in range(2):
        apadrinhar(api, novo_aluno(f"Aluno {i}"), novo_padrinho(api, f"Empresa {i}"))
    com_2 = contar()
    for i in range(2, 9):
        apadrinhar(api, novo_aluno(f"Aluno {i}"), novo_padrinho(api, f"Empresa {i}"))
    assert contar() == com_2


# ---------- Regras garantidas pelo banco ----------


def dados_da_matricula(db, matricula_id):
    db.expire_all()
    return db.execute(
        text("SELECT bolsa, padrinho_id FROM matriculas WHERE id = :id"), {"id": matricula_id}
    ).one()


def test_a_coluna_da_bolsa_comporta_apadrinhada(api, db, novo_aluno):
    """ "apadrinhada" tem 11 letras: a coluna foi alargada de 10 para 15."""
    criada = apadrinhar(api, novo_aluno(), novo_padrinho(api))
    assert dados_da_matricula(db, criada["id"]).bolsa == "apadrinhada"
    tamanho = db.scalar(
        text(
            "SELECT character_maximum_length FROM information_schema.columns"
            " WHERE table_name = 'matriculas' AND column_name = 'bolsa'"
        )
    )
    assert tamanho >= len("apadrinhada")


def test_banco_recusa_apadrinhada_sem_empresa(api, db, novo_aluno):
    criada = matricular(api, novo_aluno()["id"]).json()
    with pytest.raises(IntegrityError, match="padrinho_conforme_bolsa"):
        db.execute(
            text("UPDATE matriculas SET bolsa = 'apadrinhada' WHERE id = :id"), {"id": criada["id"]}
        )


def test_banco_recusa_empresa_numa_matricula_que_nao_e_apadrinhada(api, db, novo_aluno):
    padrinho = novo_padrinho(api)
    criada = matricular(api, novo_aluno()["id"]).json()
    with pytest.raises(IntegrityError, match="padrinho_conforme_bolsa"):
        db.execute(
            text("UPDATE matriculas SET padrinho_id = :p WHERE id = :id"),
            {"p": padrinho["id"], "id": criada["id"]},
        )


def test_banco_recusa_empresa_que_nao_existe(api, db, novo_aluno):
    criada = matricular(api, novo_aluno()["id"]).json()
    with pytest.raises(IntegrityError, match="fk_matriculas_padrinho_id_padrinhos"):
        db.execute(
            text(
                "UPDATE matriculas SET bolsa = 'apadrinhada', padrinho_id = 999999 WHERE id = :id"
            ),
            {"id": criada["id"]},
        )


def test_banco_recusa_apadrinhada_com_valor_zero(api, db, novo_aluno):
    """Quem é apadrinhado tem mensalidade de verdade: só a bolsa integral é zero."""
    criada = apadrinhar(api, novo_aluno(), novo_padrinho(api))
    with pytest.raises(IntegrityError, match="valor_conforme_bolsa"):
        db.execute(
            text("UPDATE matriculas SET valor_mensalidade = 0 WHERE id = :id"), {"id": criada["id"]}
        )


def test_banco_recusa_bolsa_desconhecida(api, db, novo_aluno):
    criada = matricular(api, novo_aluno()["id"]).json()
    with pytest.raises((IntegrityError, DataError)):
        db.execute(
            text("UPDATE matriculas SET bolsa = 'qualquer' WHERE id = :id"), {"id": criada["id"]}
        )


def test_banco_aceita_trocar_a_empresa_de_uma_matricula_apadrinhada(api, db, novo_aluno):
    primeira, segunda = novo_padrinho(api, "Primeira Ltda"), novo_padrinho(api, "Segunda Ltda")
    criada = apadrinhar(api, novo_aluno(), primeira)
    db.execute(
        update(Matricula).where(Matricula.id == criada["id"]).values(padrinho_id=segunda["id"])
    )
    db.flush()
    assert dados_da_matricula(db, criada["id"]).padrinho_id == segunda["id"]
