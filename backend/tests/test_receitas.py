import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.core import tempo
from app.db.session import engine
from app.models import Perfil, Receita

HOJE = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Os testes rodam "em 10 de novembro de 2026", para não dependerem do dia em que rodam."""
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)


def id_da(cliente, nome: str) -> int:
    """O id de uma categoria pelo nome (as iniciais já vêm cadastradas)."""
    categorias = cliente.get("/api/categorias-receita", params={"situacao": "todos"}).json()
    return next(c["id"] for c in categorias if c["nome"] == nome)


@pytest.fixture
def kits(api) -> int:
    return id_da(api, "Patrocínio")


@pytest.fixture
def viagens(api) -> int:
    return id_da(api, "Projetos e editais")


def corpo(categoria_id: int, **campos) -> dict:
    return {
        "data_receita": "2026-11-05",
        "valor": "89.90",
        "categoria_id": categoria_id,
        "descricao": "Patrocínio da feira de ciências",
        "origem": "Mineração Vale Verde",
    } | campos


def registrar(cliente, categoria_id: int, **campos):
    return cliente.post("/api/receitas", json=corpo(categoria_id, **campos))


def criar(cliente, categoria_id: int, **campos) -> dict:
    resposta = registrar(cliente, categoria_id, **campos)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def listar(cliente, **filtros) -> list[dict]:
    resposta = cliente.get("/api/receitas", params=filtros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


def no_banco(db) -> list[Receita]:
    db.expire_all()
    return list(db.scalars(select(Receita).order_by(Receita.id)))


# ---------- Registrar ----------


def test_registra_uma_receita(api, db, kits):
    eu = api.get("/api/auth/eu").json()

    resposta = registrar(api, kits)

    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["registrado_em"]
    assert dados | {"id": 0, "registrado_em": ""} == {
        "id": 0,
        "data_receita": "2026-11-05",
        "valor": "89.90",
        "categoria": {"id": kits, "nome": "Patrocínio", "ativo": True},
        "descricao": "Patrocínio da feira de ciências",
        "origem": "Mineração Vale Verde",
        "registrado_por": eu["nome"],
        "registrado_em": "",
        "cancelamento": None,
        "substitui_id": None,
        "substituida_por_id": None,
    }
    assert len(no_banco(db)) == 1


def test_guarda_quem_registrou_e_quando(api_como, db, kits):
    """RF26: cada receita guarda o usuário e o momento do registro."""
    operador = api_como(Perfil.OPERADOR)
    nome_do_operador = operador.get("/api/auth/eu").json()["nome"]

    criar(operador, kits)

    receita = no_banco(db)[0]
    assert receita.criado_por.nome == nome_do_operador
    assert receita.criado_em.year >= 2026


def test_cada_receita_mostra_quem_a_registrou(api, api_como, kits):
    outro = api_como(Perfil.OPERADOR)
    criar(api, kits, descricao="Feita pelo administrador")
    criar(outro, kits, descricao="Feita pelo operador")

    por_descricao = {d["descricao"]: d["registrado_por"] for d in listar(api)}

    assert por_descricao["Feita pelo administrador"] == api.get("/api/auth/eu").json()["nome"]
    assert por_descricao["Feita pelo operador"] == outro.get("/api/auth/eu").json()["nome"]
    assert len(set(por_descricao.values())) == 2


def test_a_receita_nao_expoe_dados_do_usuario_alem_do_nome(api, kits):
    dados = criar(api, kits)
    assert "email" not in str(dados)
    assert "criado_por" not in dados


def test_campos_extras_sao_ignorados(api, db, kits):
    resposta = registrar(
        api, kits, id=999, criado_em="2000-01-01T00:00:00", criado_por_id=999999, cancelado=True
    )

    assert resposta.status_code == 201
    assert resposta.json()["id"] != 999
    receita = no_banco(db)[0]
    assert receita.criado_em.year >= 2026
    assert receita.criado_por_id != 999999


def test_pode_registrar_na_mesma_categoria_varias_receitas_iguais(api, kits):
    """Duas receitas iguais no mesmo dia são possíveis: não há regra de unicidade."""
    criar(api, kits)
    criar(api, kits)
    assert len(listar(api)) == 2


def test_texto_e_valores_sao_guardados_limpos(api, db, kits):
    criar(api, kits, descricao="  Placa   de \n robô  ", origem="  Mineração   Vale Verde  ")
    receita = no_banco(db)[0]
    assert receita.descricao == "Placa de robô"
    assert receita.origem == "Mineração Vale Verde"


def test_corpo_vazio_aponta_os_quatro_campos_em_portugues(api):
    erros = erros_de(api.post("/api/receitas", json={}))

    assert erros == {
        "data_receita": "Informe a data da receita",
        "valor": "Informe o valor da receita",
        "categoria_id": "Escolha a categoria da receita",
        "origem": "Informe quem pagou",
    }


def test_corpo_que_nao_e_um_objeto_da_422(api):
    assert api.post("/api/receitas", json=["x"]).status_code == 422
    assert api.post("/api/receitas", json="x").status_code == 422
    resposta = api.post(
        "/api/receitas",
        content="{isto não é json",
        headers={"Content-Type": "application/json"},
    )
    assert resposta.status_code == 422


def test_os_quatro_campos_constam_como_obrigatorios_no_openapi(api):
    esquema = api.get("/openapi.json").json()["components"]["schemas"]["ReceitaEntrada"]
    assert set(esquema["required"]) == {
        "data_receita",
        "valor",
        "categoria_id",
        "origem",
    }


# ---------- Valor (RN09) ----------


@pytest.mark.parametrize(
    ("enviado", "guardado"),
    [
        ("89.90", "89.90"),
        ("89,90", "89.90"),
        (" 89,9 ", "89.90"),
        (89.9, "89.90"),
        (100, "100.00"),
        ("100", "100.00"),
        ("0.01", "0.01"),
        ("0,01", "0.01"),
        ("99999999.99", "99999999.99"),
        ("12.5", "12.50"),
    ],
)
def test_aceita_valores_validos_e_guarda_com_duas_casas(api, kits, enviado, guardado):
    assert criar(api, kits, valor=enviado)["valor"] == guardado


@pytest.mark.parametrize(
    ("valor", "mensagem"),
    [
        ("0", "O valor da receita deve ser maior que zero"),
        ("0.00", "O valor da receita deve ser maior que zero"),
        ("-5", "O valor da receita deve ser maior que zero"),
        ("-0,01", "O valor da receita deve ser maior que zero"),
        (0, "O valor da receita deve ser maior que zero"),
        (-1, "O valor da receita deve ser maior que zero"),
        ("10.123", "Use no máximo 2 casas decimais"),
        ("0.001", "Use no máximo 2 casas decimais"),
        ("100000000", "O valor da receita é alto demais"),
        ("100000000.00", "O valor da receita é alto demais"),
        ("99999999999999999999", "O valor da receita é alto demais"),
        ("", "Informe o valor da receita"),
        ("   ", "Informe o valor da receita"),
        (None, "Informe o valor da receita"),
        ("abc", "Informe um valor válido"),
        ("R$ 10", "Informe um valor válido"),
        ("1.000,50", "Informe um valor válido"),
        ("NaN", "Informe um valor válido"),
        ("nan", "Informe um valor válido"),
        ("Infinity", "Informe um valor válido"),
        ("-Infinity", "Informe um valor válido"),
        ("inf", "Informe um valor válido"),
        (True, "Informe um valor válido"),
        ([], "Informe um valor válido"),
        ({}, "Informe um valor válido"),
        ([1], "Informe um valor válido"),
    ],
)
def test_recusa_valor_invalido_em_portugues(api, db, kits, valor, mensagem):
    assert erros_de(registrar(api, kits, valor=valor))["valor"] == mensagem
    assert no_banco(db) == []


def test_valor_nan_enviado_como_numero_de_json_da_422_e_nao_500(api, kits):
    """O JSON do Python aceita NaN e Infinity soltos: a resposta de erro não pode quebrar."""
    for solto in ("NaN", "Infinity", "-Infinity"):
        texto = json.dumps(corpo(kits, valor="VALOR")).replace('"VALOR"', solto)
        resposta = api.post(
            "/api/receitas", content=texto, headers={"Content-Type": "application/json"}
        )
        assert resposta.status_code == 422, resposta.text


# ---------- Data (RN09) ----------


@pytest.mark.parametrize("data", ["2026-11-10", "2026-11-09", "2026-01-01", "2000-01-01"])
def test_aceita_data_de_hoje_e_do_passado(api, kits, data):
    assert criar(api, kits, data_receita=data)["data_receita"] == data


@pytest.mark.parametrize("data", ["2026-11-11", "2026-12-01", "2027-01-01", "9999-12-31"])
def test_recusa_data_no_futuro(api, db, kits, data):
    erros = erros_de(registrar(api, kits, data_receita=data))
    assert erros["data_receita"] == "A data da receita não pode ser no futuro"
    assert no_banco(db) == []


def test_recusa_data_antiga_demais(api, kits):
    erros = erros_de(registrar(api, kits, data_receita="1999-12-31"))
    assert erros["data_receita"] == "Essa data é antiga demais"


@pytest.mark.parametrize("data", ["", "   ", None])
def test_recusa_data_em_branco_em_portugues(api, kits, data):
    erros = erros_de(registrar(api, kits, data_receita=data))
    assert erros["data_receita"] == "Informe a data da receita"


@pytest.mark.parametrize(
    "data", ["10/11/2026", "2026-02-30", "abc", "2026-13-01", "0000-00-00", ["2026-11-05"], {}]
)
def test_recusa_data_em_formato_invalido(api, db, kits, data):
    assert "data_receita" in erros_de(registrar(api, kits, data_receita=data))
    assert no_banco(db) == []


def test_a_data_do_futuro_segue_o_relogio_de_brasilia(api, kits, monkeypatch):
    """O que vale é a data de "hoje" do sistema (horário de Brasília), não a do servidor."""
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 30))
    assert registrar(api, kits, data_receita="2026-11-30").status_code == 201
    assert registrar(api, kits, data_receita="2026-12-01").status_code == 422


# ---------- Categoria (RN08) ----------


def test_toda_receita_tem_categoria(api, db):
    dados = corpo(0)
    del dados["categoria_id"]

    resposta = api.post("/api/receitas", json=dados)

    assert erros_de(resposta)["categoria_id"] == "Escolha a categoria da receita"
    assert no_banco(db) == []


@pytest.mark.parametrize("categoria", [None, "", "  ", True, False, 0, -1, 2147483648, 10**20])
def test_recusa_categoria_em_branco_ou_fora_do_intervalo(api, db, categoria):
    erros = erros_de(registrar(api, categoria))
    assert erros["categoria_id"] == "Escolha a categoria da receita"
    assert no_banco(db) == []


@pytest.mark.parametrize("categoria", ["abc", 1.5, [1], {}])
def test_recusa_categoria_que_nao_e_um_numero(api, db, categoria):
    assert "categoria_id" in erros_de(registrar(api, categoria))
    assert no_banco(db) == []


def test_categoria_que_nao_existe_da_422(api, db):
    resposta = registrar(api, 999999)

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Categoria não encontrada"
    assert no_banco(db) == []


def test_o_maior_id_possivel_passa_pela_validacao_e_nao_e_encontrado(api, db):
    """2147483647 cabe no inteiro do banco: não pode virar erro 500, só "não encontrada"."""
    resposta = registrar(api, 2147483647)

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Categoria não encontrada"
    assert no_banco(db) == []


def test_categoria_inativa_nao_recebe_receita_nova(api, db, kits):
    api.put(f"/api/categorias-receita/{kits}", json={"nome": "Patrocínio", "ativo": False})

    resposta = registrar(api, kits)

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == (
        "Categoria inativa não recebe receitas. Reative a categoria antes."
    )
    assert no_banco(db) == []


def test_categoria_reativada_volta_a_receber_receita(api, kits):
    url = f"/api/categorias-receita/{kits}"
    api.put(url, json={"nome": "Patrocínio", "ativo": False})
    api.put(url, json={"nome": "Patrocínio", "ativo": True})

    assert registrar(api, kits).status_code == 201


def test_receita_antiga_continua_visivel_depois_de_inativar_a_categoria(api, kits):
    criar(api, kits, descricao="Compra antiga")
    api.put(f"/api/categorias-receita/{kits}", json={"nome": "Patrocínio", "ativo": False})

    lista = listar(api)

    assert [d["descricao"] for d in lista] == ["Compra antiga"]
    assert lista[0]["categoria"] == {"id": kits, "nome": "Patrocínio", "ativo": False}


def test_renomear_a_categoria_aparece_nas_receitas_ja_lancadas(api, kits):
    criar(api, kits)
    api.put(f"/api/categorias-receita/{kits}", json={"nome": "Patrocínio e apoio", "ativo": True})

    assert listar(api)[0]["categoria"]["nome"] == "Patrocínio e apoio"


def test_uma_categoria_criada_por_voce_recebe_receita(api):
    categoria = api.post("/api/categorias-receita", json={"nome": "Uniformes"}).json()
    assert criar(api, categoria["id"])["categoria"]["nome"] == "Uniformes"


# ---------- Descrição e origem ----------


@pytest.mark.parametrize("valor", ["", "   ", None, 5, True, ["x"], {"a": 1}])
def test_recusa_origem_vazia_ou_de_tipo_errado(api, db, kits, valor):
    # RN08: toda entrada tem origem
    assert "origem" in erros_de(registrar(api, kits, origem=valor))
    assert no_banco(db) == []


@pytest.mark.parametrize("valor", ["", "   ", None])
def test_descricao_e_opcional(api, kits, valor):
    resposta = registrar(api, kits, descricao=valor)
    assert resposta.status_code == 201
    assert resposta.json()["descricao"] is None


def test_descricao_pode_nem_vir_no_corpo(api, kits):
    corpo = {
        "data_receita": "2026-11-05",
        "valor": "500",
        "categoria_id": kits,
        "origem": "Prefeitura de João Monlevade",
    }
    resposta = api.post("/api/receitas", json=corpo)
    assert resposta.status_code == 201
    assert resposta.json()["descricao"] is None


@pytest.mark.parametrize("valor", [5, True, ["x"], {"a": 1}])
def test_descricao_de_tipo_errado_vira_422(api, db, kits, valor):
    assert "descricao" in erros_de(registrar(api, kits, descricao=valor))
    assert no_banco(db) == []


@pytest.mark.parametrize(
    ("campo", "menor", "maior"),
    [("descricao", 3, 255), ("origem", 2, 120)],
)
def test_limites_de_tamanho_do_texto(api, kits, campo, menor, maior):
    assert registrar(api, kits, **{campo: "a" * menor}).status_code == 201
    assert registrar(api, kits, **{campo: "a" * maior}).status_code == 201
    assert campo in erros_de(registrar(api, kits, **{campo: "a" * (menor - 1)}))
    assert campo in erros_de(registrar(api, kits, **{campo: "a" * (maior + 1)}))


def test_mensagens_do_texto_sao_em_portugues(api, kits):
    assert erros_de(registrar(api, kits, descricao="ab"))["descricao"] == (
        "A descrição deve ter pelo menos 3 letras"
    )
    assert erros_de(registrar(api, kits, descricao="a" * 256))["descricao"] == (
        "A descrição deve ter no máximo 255 caracteres"
    )
    assert erros_de(registrar(api, kits, origem=""))["origem"] == "Informe quem pagou"
    assert erros_de(registrar(api, kits, origem="a"))["origem"] == (
        "A origem deve ter pelo menos 2 letras"
    )
    assert erros_de(registrar(api, kits, origem="a" * 121))["origem"] == (
        "A origem deve ter no máximo 120 caracteres"
    )


@pytest.mark.parametrize("campo", ["descricao", "origem"])
def test_recusa_caractere_nulo_no_texto(api, db, kits, campo):
    erros = erros_de(registrar(api, kits, **{campo: "texto" + chr(0) + "nulo"}))
    assert erros[campo] == "O texto tem um caractere inválido"
    assert no_banco(db) == []


def test_os_espacos_contam_depois_de_limpos(api, kits):
    """ "a" mais muitos espaços não vira um texto de tamanho 255: vale o texto já limpo."""
    assert registrar(api, kits, descricao="ab" + " " * 300).status_code == 422
    assert (
        registrar(api, kits, descricao="a" + " " * 300 + "b" + " " * 300 + "c").status_code == 201
    )


def test_unicode_invalido_nao_da_500(api, kits):
    """Um "\\ud800" solto no JSON não é texto válido: tem de virar 422, não erro 500."""
    texto = json.dumps(corpo(kits, descricao="TEXTO")).replace('"TEXTO"', '"\\ud800 solto"')
    resposta = api.post(
        "/api/receitas", content=texto, headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 422


# ---------- Listar, filtrar e totais do período ----------


def test_lista_vazia_no_comeco(api):
    assert listar(api) == []


def test_lista_da_mais_recente_para_a_mais_antiga(api, kits):
    criar(api, kits, data_receita="2026-11-01", descricao="Primeira")
    criar(api, kits, data_receita="2026-11-09", descricao="Terceira")
    criar(api, kits, data_receita="2026-11-05", descricao="Segunda")
    criar(api, kits, data_receita="2026-11-09", descricao="Quarta (mesmo dia, lançada depois)")

    assert [d["descricao"] for d in listar(api)] == [
        "Quarta (mesmo dia, lançada depois)",
        "Terceira",
        "Segunda",
        "Primeira",
    ]


def test_no_mesmo_dia_a_mais_nova_vem_primeiro_sempre(api, kits):
    """Sem desempate, a ordem entre receitas do mesmo dia ficaria ao acaso."""
    for i in range(15):
        criar(api, kits, data_receita="2026-11-05", descricao=f"Receita {i:02d}")

    ids = [d["id"] for d in listar(api)]

    assert ids == sorted(ids, reverse=True)


def test_filtra_por_mes_incluindo_o_primeiro_e_o_ultimo_dia(api, kits):
    criar(api, kits, data_receita="2026-10-31", descricao="Outubro")
    criar(api, kits, data_receita="2026-11-01", descricao="Novembro dia 1")
    criar(api, kits, data_receita="2026-11-09", descricao="Novembro dia 9")

    assert [d["descricao"] for d in listar(api, mes="2026-11")] == [
        "Novembro dia 9",
        "Novembro dia 1",
    ]
    assert [d["descricao"] for d in listar(api, mes="2026-10")] == ["Outubro"]
    assert listar(api, mes="2026-09") == []


def test_o_mes_de_dezembro_vai_ate_o_dia_31_e_nao_pega_janeiro(api, kits, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 2, 1))
    criar(api, kits, data_receita="2026-11-30", descricao="Novembro")
    criar(api, kits, data_receita="2026-12-01", descricao="Dezembro dia 1")
    criar(api, kits, data_receita="2026-12-31", descricao="Dezembro dia 31")
    criar(api, kits, data_receita="2027-01-01", descricao="Janeiro")

    assert [d["descricao"] for d in listar(api, mes="2026-12")] == [
        "Dezembro dia 31",
        "Dezembro dia 1",
    ]


def test_mes_vazio_ou_ausente_traz_todos_os_meses(api, kits):
    criar(api, kits, data_receita="2026-10-31")
    criar(api, kits, data_receita="2026-11-01")

    assert len(listar(api)) == 2
    assert len(listar(api, mes="")) == 2
    assert len(listar(api, mes="   ")) == 2


def test_o_mes_aceita_uma_data_completa(api, kits):
    criar(api, kits, data_receita="2026-11-01")
    assert len(listar(api, mes="2026-11-25")) == 1


@pytest.mark.parametrize(
    "mes", ["2026-13", "2026-00", "abc", "2026", "11/2026", "2026-1", "x" * 10]
)
def test_mes_invalido_da_422_no_formato_padrao(api, mes):
    resposta = api.get("/api/receitas", params={"mes": mes})
    assert "mes" in erros_de(resposta)


def test_mes_comprido_demais_da_422(api):
    assert api.get("/api/receitas", params={"mes": "2026-11-05-extra"}).status_code == 422


def test_filtra_por_categoria(api, kits, viagens):
    criar(api, kits, descricao="Placa")
    criar(api, viagens, descricao="Passagem")

    assert [d["descricao"] for d in listar(api, categoria_id=kits)] == ["Placa"]
    assert [d["descricao"] for d in listar(api, categoria_id=viagens)] == ["Passagem"]
    assert len(listar(api)) == 2


def test_categoria_sem_receitas_devolve_lista_vazia(api, kits):
    assert listar(api, categoria_id=kits) == []
    assert listar(api, categoria_id=999999) == []


@pytest.mark.parametrize("categoria_id", ["0", "-1", "abc", "2147483648"])
def test_categoria_do_filtro_invalida_da_422(api, categoria_id):
    assert api.get("/api/receitas", params={"categoria_id": categoria_id}).status_code == 422


def test_busca_na_descricao_e_na_origem_sem_diferenciar_maiusculas(api, kits):
    criar(api, kits, descricao="Patrocínio da feira", origem="Empresa Alfa")
    criar(api, kits, descricao="Cabos", origem="Casa dos Robôs")

    assert [d["descricao"] for d in listar(api, busca="FEIRA")] == ["Patrocínio da feira"]
    assert [d["descricao"] for d in listar(api, busca="casa dos")] == ["Cabos"]
    assert [d["descricao"] for d in listar(api, busca="  alfa  ")] == ["Patrocínio da feira"]
    assert listar(api, busca="nada disso") == []


def test_busca_trata_porcentagem_e_sublinhado_como_texto(api, kits):
    criar(api, kits, descricao="Desconto de 10% na loja")
    criar(api, kits, descricao="Item_especial")
    criar(api, kits, descricao="Item comum")

    assert [d["descricao"] for d in listar(api, busca="%")] == ["Desconto de 10% na loja"]
    assert [d["descricao"] for d in listar(api, busca="_")] == ["Item_especial"]


def test_caractere_nulo_na_busca_e_ignorado(api, kits):
    criar(api, kits, descricao="Placa")
    assert len(listar(api, busca="Pl" + chr(0) + "aca")) == 1
    assert len(listar(api, busca=chr(0))) == 1


def test_filtros_combinados(api, kits, viagens):
    criar(api, kits, data_receita="2026-11-02", descricao="Placa nova")
    criar(api, kits, data_receita="2026-10-02", descricao="Placa velha")
    criar(api, viagens, data_receita="2026-11-03", descricao="Placa na mala")
    criar(api, kits, data_receita="2026-11-04", descricao="Cabos")

    achadas = listar(api, mes="2026-11", categoria_id=kits, busca="placa")

    assert [d["descricao"] for d in achadas] == ["Placa nova"]


def test_o_total_do_periodo_fecha_com_a_soma_dos_valores(api, kits, viagens):
    """A tela soma os valores devolvidos: eles vêm exatos, com duas casas, sem arredondar."""
    criar(api, kits, valor="0.10")
    criar(api, kits, valor="0.20")
    criar(api, viagens, valor="1234.56")

    valores = [d["valor"] for d in listar(api, mes="2026-11")]

    assert sorted(valores) == ["0.10", "0.20", "1234.56"]
    assert sum(Decimal(v) for v in valores) == Decimal("1234.86")


def test_a_resposta_traz_o_necessario_para_a_tela(api, kits):
    criar(api, kits)

    assert set(listar(api)[0]) == {
        "id",
        "data_receita",
        "valor",
        "categoria",
        "descricao",
        "origem",
        "registrado_por",
        "registrado_em",
        "cancelamento",
        "substitui_id",
        "substituida_por_id",
    }


def test_a_lista_nao_faz_uma_consulta_por_linha(api, api_como, db, kits, viagens):
    def contar() -> int:
        total = 0

        def conta(*_):
            nonlocal total
            total += 1

        db.expire_all()
        event.listen(engine, "before_cursor_execute", conta)
        try:
            assert api.get("/api/receitas").status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", conta)
        return total

    criar(api, kits)
    com_uma = contar()

    # Usuários e categorias diferentes em cada linha: sem carregar junto, seriam consultas a mais
    for i in range(8):
        cliente = api_como(Perfil.OPERADOR)
        criar(cliente, viagens if i % 2 else kits, descricao=f"Receita {i}")
    com_nove = contar()

    assert com_nove == com_uma


# ---------- Perfis (RN13) ----------


def test_sem_login_nao_acessa_nada(sem_login):
    assert sem_login.get("/api/receitas").status_code == 401
    assert sem_login.post("/api/receitas", json=corpo(1)).status_code == 401


def test_token_invalido_nao_acessa(sem_login):
    resposta = sem_login.get("/api/receitas", headers={"Authorization": "Bearer x"})
    assert resposta.status_code == 401


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_consultam(api, api_como, kits, perfil):
    criada = criar(api, kits)
    cliente = api_como(perfil)
    assert [d["id"] for d in listar(cliente)] == [criada["id"]]


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.ADMINISTRADOR])
def test_operador_e_administrador_registram(api, api_como, kits, perfil):
    assert registrar(api_como(perfil), kits).status_code == 201


def test_consulta_so_visualiza(api, api_como, db, kits):
    consulta = api_como(Perfil.CONSULTA)

    assert registrar(consulta, kits).status_code == 403
    assert no_banco(db) == []


def test_o_perfil_e_conferido_antes_de_tudo(api_como):
    """A consulta não descobre se a categoria existe nem se os dados estão certos."""
    consulta = api_como(Perfil.CONSULTA)

    assert registrar(consulta, 999999).status_code == 403
    assert consulta.post("/api/receitas", json={}).status_code == 403


# ---------- Nada é apagado nem alterado (RN12) ----------


def test_nao_ha_como_apagar_nem_alterar_uma_receita(api, db, kits):
    criada = criar(api, kits)
    url = f"/api/receitas/{criada['id']}"

    # Não existe rota para uma receita específica: nenhum método chega nela
    for metodo in ("DELETE", "PUT", "PATCH", "GET"):
        assert api.request(metodo, url).status_code in (404, 405)
    # E a lista não aceita apagar nem alterar tudo de uma vez
    assert api.delete("/api/receitas").status_code == 405
    assert api.put("/api/receitas", json=corpo(kits)).status_code == 405
    assert api.patch("/api/receitas", json={}).status_code == 405

    assert len(no_banco(db)) == 1
    assert listar(api)[0] == criada


# ---------- Restrições do banco ----------


def test_o_banco_recusa_valor_zero_mesmo_sem_passar_pela_api(api, db, kits):
    receita = Receita(
        data_receita=HOJE,
        valor=0,
        categoria_id=kits,
        descricao="Zero",
        origem="Ninguém",
        criado_por_id=api.get("/api/auth/eu").json()["id"],
    )
    db.add(receita)
    with pytest.raises(IntegrityError, match="ck_receitas_valor_positivo"):
        db.flush()
    db.rollback()
