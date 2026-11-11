import json

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models import CategoriaDespesa, Perfil, Usuario
from app.routers import categorias_despesa as rota_categorias

# As categorias que a migração já cadastra (RF15)
INICIAIS = [
    "Kits de robótica",
    "Viagens",
    "Custos fixos",
    "Professores",
    "Peças",
    "Inscrições em competições",
]


def corpo(**campos) -> dict:
    return {"nome": "Uniformes"} | campos


def cadastrar(cliente, **campos):
    return cliente.post("/api/categorias-despesa", json=corpo(**campos))


def criar(cliente, **campos) -> dict:
    resposta = cadastrar(cliente, **campos)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def editar(cliente, categoria_id, **campos):
    return cliente.put(f"/api/categorias-despesa/{categoria_id}", json=corpo(**campos))


def nomes(cliente, **filtros) -> list[str]:
    resposta = cliente.get("/api/categorias-despesa", params=filtros)
    assert resposta.status_code == 200, resposta.text
    return [c["nome"] for c in resposta.json()]


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


def no_banco(db) -> list[str]:
    """Nomes de todas as categorias gravadas, inclusive as iniciais."""
    db.expire_all()
    return list(db.scalars(select(CategoriaDespesa.nome).order_by(CategoriaDespesa.id)))


# ---------- As categorias iniciais (RF15) ----------


def test_ja_vem_com_as_categorias_iniciais(api):
    todas = api.get("/api/categorias-despesa", params={"situacao": "todos"}).json()
    por_nome = {c["nome"]: c for c in todas}

    for nome in INICIAIS:
        assert por_nome[nome]["ativo"] is True


def test_as_iniciais_aparecem_na_lista_padrao_em_ordem_alfabetica(api):
    lista = nomes(api)
    iniciais_na_lista = [n for n in lista if n in INICIAIS]

    assert sorted(iniciais_na_lista) == sorted(INICIAIS)
    # "Aaa" vem antes de qualquer inicial e "Zzz" depois de todas, em qualquer ordenação de letras
    criar(api, nome="Aaa Teste")
    criar(api, nome="Zzz Teste")
    lista = nomes(api)
    assert lista[0] == "Aaa Teste"
    assert lista[-1] == "Zzz Teste"
    assert lista.index("Aaa Teste") < lista.index("Custos fixos") < lista.index("Zzz Teste")


# ---------- Cadastrar ----------


def test_cadastra_uma_categoria(api, db):
    resposta = cadastrar(api)

    assert resposta.status_code == 201
    assert resposta.json() == {"id": resposta.json()["id"], "nome": "Uniformes", "ativo": True}
    assert "Uniformes" in no_banco(db)


def test_a_categoria_cadastrada_pode_ser_consultada_depois(api):
    criada = criar(api)
    assert api.get(f"/api/categorias-despesa/{criada['id']}").json() == criada


def test_limpa_espacos_do_nome(api):
    assert criar(api, nome="  Material    de \n escritório  ")["nome"] == "Material de escritório"


def test_campos_extras_sao_ignorados(api):
    resposta = cadastrar(api, id=999, criado_em="2000-01-01T00:00:00", papel="admin")
    assert resposta.status_code == 201
    assert resposta.json()["id"] != 999


def test_cadastra_ja_inativa(api):
    assert criar(api, ativo=False)["ativo"] is False
    assert "Uniformes" not in nomes(api)


@pytest.mark.parametrize("nome", ["", " ", "a", None, 5, True, ["x"], {"a": 1}, "x" * 61])
def test_recusa_nome_invalido(api, db, nome):
    antes = no_banco(db)
    assert "nome" in erros_de(cadastrar(api, nome=nome))
    assert no_banco(db) == antes


def test_limites_do_nome(api):
    assert cadastrar(api, nome="ab").status_code == 201
    assert cadastrar(api, nome="a" * 60).status_code == 201


def test_mensagens_do_nome_sao_em_portugues(api):
    assert erros_de(cadastrar(api, nome=""))["nome"] == "Informe o nome da categoria"
    assert erros_de(cadastrar(api, nome=None))["nome"] == "Informe o nome da categoria"
    assert erros_de(cadastrar(api, nome="a"))["nome"] == (
        "O nome da categoria deve ter pelo menos 2 letras"
    )
    assert erros_de(cadastrar(api, nome="a" * 61))["nome"] == (
        "O nome da categoria deve ter no máximo 60 caracteres"
    )


def test_nome_sem_o_campo_da_422_em_portugues(api):
    resposta = api.post("/api/categorias-despesa", json={})
    assert erros_de(resposta)["nome"] == "Informe o nome da categoria"


def test_recusa_caractere_nulo_no_nome(api):
    erros = erros_de(cadastrar(api, nome="texto" + chr(0) + "nulo"))
    assert erros["nome"] == "O texto tem um caractere inválido"


def test_unicode_invalido_no_nome_da_422_e_nao_500(api):
    """Um "\\ud800" solto no JSON não é texto válido: tem de virar 422, não erro 500."""
    texto = json.dumps({"nome": "TEXTO"}).replace('"TEXTO"', '"\\ud800 solto"')
    resposta = api.post(
        "/api/categorias-despesa", content=texto, headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 422


@pytest.mark.parametrize("ativo", [0, 1, "no", "false", "sim", None, "", [], {}])
def test_ativo_so_vale_verdadeiro_ou_falso(api, db, ativo):
    antes = no_banco(db)
    assert erros_de(cadastrar(api, ativo=ativo))["ativo"] == "Informe verdadeiro ou falso"
    assert no_banco(db) == antes


def test_corpo_que_nao_e_um_objeto_da_422(api):
    assert api.post("/api/categorias-despesa", json=["Uniformes"]).status_code == 422
    assert api.post("/api/categorias-despesa", json="Uniformes").status_code == 422


# ---------- Nome repetido ----------


def test_nome_repetido_da_409(api, db):
    criar(api, nome="Uniformes")

    resposta = cadastrar(api, nome="Uniformes")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe uma categoria com este nome"
    assert no_banco(db).count("Uniformes") == 1


@pytest.mark.parametrize(
    ("existente", "repetido"),
    [
        ("Uniformes", "UNIFORMES"),
        ("Uniformes", "uniformes"),
        ("Uniformes", "  Uniformes  "),
        ("Uni formes", "Uni   formes"),
    ],
)
def test_nome_repetido_nao_diferencia_maiusculas_nem_espacos(api, existente, repetido):
    criar(api, nome=existente)
    assert cadastrar(api, nome=repetido).status_code == 409


def test_nao_se_repete_nome_de_categoria_inicial(api):
    assert cadastrar(api, nome="Viagens").status_code == 409
    assert cadastrar(api, nome="VIAGENS").status_code == 409
    assert cadastrar(api, nome="custos fixos").status_code == 409


def test_nome_de_categoria_inativa_tambem_conta_como_repetido(api):
    criar(api, nome="Uniformes", ativo=False)
    assert cadastrar(api, nome="Uniformes").status_code == 409


def test_nomes_parecidos_nao_sao_repetidos(api):
    criar(api, nome="Uniformes")
    assert cadastrar(api, nome="Uniformes novos").status_code == 201
    assert cadastrar(api, nome="Uniforme").status_code == 201


def test_corrida_entre_dois_cadastros_do_mesmo_nome_vira_409_e_nao_500(api, db, monkeypatch):
    """Os dois pedidos passam pela conferência prévia: só o índice único do banco os separa."""
    criar(api, nome="Uniformes")
    monkeypatch.setattr(rota_categorias, "exige_nome_livre", lambda *args, **kwargs: None)

    resposta = cadastrar(api, nome="UNIFORMES")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe uma categoria com este nome"
    assert [n.lower() for n in no_banco(db)].count("uniformes") == 1


def test_corrida_na_edicao_tambem_vira_409(api, db, monkeypatch):
    criar(api, nome="Uniformes")
    outra = criar(api, nome="Brindes")
    monkeypatch.setattr(rota_categorias, "exige_nome_livre", lambda *args, **kwargs: None)

    resposta = editar(api, outra["id"], nome="uniformes")

    assert resposta.status_code == 409
    assert "Brindes" in no_banco(db)


def test_outro_erro_de_integridade_nao_e_escondido_como_409(api, monkeypatch):
    """Só o nome repetido vira 409: qualquer outra violação do banco continua sendo um erro real."""

    def quebra(*args, **kwargs):
        raise IntegrityError("INSERT", {}, Exception("outra_restricao"))

    monkeypatch.setattr(rota_categorias.Session, "commit", quebra, raising=False)
    with pytest.raises(IntegrityError):
        cadastrar(api)


# ---------- Editar, desativar e reativar ----------


def test_edita_o_nome(api, db):
    criada = criar(api)

    resposta = editar(api, criada["id"], nome="Camisetas")

    assert resposta.status_code == 200
    assert resposta.json() == {"id": criada["id"], "nome": "Camisetas", "ativo": True}
    assert "Camisetas" in no_banco(db)
    assert "Uniformes" not in no_banco(db)


def test_salvar_com_o_mesmo_nome_nao_da_conflito(api):
    criada = criar(api)
    assert editar(api, criada["id"], nome="Uniformes").status_code == 200
    # Mudar só as maiúsculas da própria categoria também vale
    assert editar(api, criada["id"], nome="UNIFORMES").json()["nome"] == "UNIFORMES"


def test_editar_para_o_nome_de_outra_da_409_e_nada_muda(api, db):
    criar(api, nome="Uniformes")
    segunda = criar(api, nome="Brindes")

    resposta = editar(api, segunda["id"], nome="uniformes")

    assert resposta.status_code == 409
    assert "Brindes" in no_banco(db)


def test_pode_renomear_uma_categoria_inicial(api):
    inicial = next(c for c in api.get("/api/categorias-despesa").json() if c["nome"] == "Peças")
    assert editar(api, inicial["id"], nome="Peças de robôs").json()["nome"] == "Peças de robôs"


def test_desativa_e_reativa(api):
    criada = criar(api)

    desativada = editar(api, criada["id"], ativo=False)
    assert desativada.status_code == 200
    assert desativada.json()["ativo"] is False
    assert "Uniformes" not in nomes(api)
    assert "Uniformes" in nomes(api, situacao="inativos")

    reativada = editar(api, criada["id"], ativo=True)
    assert reativada.json()["ativo"] is True
    assert "Uniformes" in nomes(api)


@pytest.mark.parametrize("ativo", [0, 1, "no", "off", None, "false"])
def test_ativo_torto_na_edicao_nao_desativa_em_silencio(api, ativo):
    criada = criar(api)

    assert "ativo" in erros_de(editar(api, criada["id"], ativo=ativo))
    assert api.get(f"/api/categorias-despesa/{criada['id']}").json()["ativo"] is True


@pytest.mark.parametrize("nome", ["", "a", None, "x" * 61])
def test_edicao_com_nome_invalido_da_422_e_nada_muda(api, nome):
    criada = criar(api)
    assert "nome" in erros_de(editar(api, criada["id"], nome=nome))
    assert api.get(f"/api/categorias-despesa/{criada['id']}").json() == criada


def test_editar_categoria_que_nao_existe_da_404(api):
    resposta = editar(api, 999999)
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Categoria não encontrada"


def test_consultar_categoria_que_nao_existe_da_404(api):
    assert api.get("/api/categorias-despesa/999999").status_code == 404


@pytest.mark.parametrize("categoria_id", ["0", "-1", "abc", "2147483648", "99999999999999999999"])
def test_id_invalido_da_422(api, categoria_id):
    assert api.get(f"/api/categorias-despesa/{categoria_id}").status_code == 422
    assert api.put(f"/api/categorias-despesa/{categoria_id}", json=corpo()).status_code == 422


def test_categoria_nunca_e_apagada(api, db):
    criada = criar(api)

    assert api.delete(f"/api/categorias-despesa/{criada['id']}").status_code == 405
    assert api.delete("/api/categorias-despesa").status_code == 405
    assert api.patch(f"/api/categorias-despesa/{criada['id']}", json={}).status_code == 405
    assert "Uniformes" in no_banco(db)


# ---------- Listar ----------


def test_a_lista_padrao_so_traz_as_ativas(api):
    criar(api, nome="Ativa Teste")
    criar(api, nome="Inativa Teste", ativo=False)

    lista = nomes(api)

    assert "Ativa Teste" in lista
    assert "Inativa Teste" not in lista


def test_filtra_por_situacao(api):
    criar(api, nome="Ativa Teste")
    criar(api, nome="Inativa Teste", ativo=False)

    assert nomes(api, situacao="ativos").count("Inativa Teste") == 0
    assert nomes(api, situacao="inativos") == ["Inativa Teste"]
    todas = nomes(api, situacao="todos")
    assert "Ativa Teste" in todas
    assert "Inativa Teste" in todas


def test_situacao_desconhecida_da_422(api):
    assert api.get("/api/categorias-despesa", params={"situacao": "quase"}).status_code == 422


def test_busca_pelo_nome_sem_diferenciar_maiusculas(api):
    assert nomes(api, busca="viagens") == ["Viagens"]
    assert nomes(api, busca="VIAGENS") == ["Viagens"]
    assert nomes(api, busca="  viag  ") == ["Viagens"]
    assert nomes(api, busca="nenhuma categoria assim") == []


def test_busca_trata_porcentagem_e_sublinhado_como_texto(api):
    criar(api, nome="Taxa 50% da rifa")
    criar(api, nome="Rifa_beneficente")

    assert nomes(api, busca="%") == ["Taxa 50% da rifa"]
    assert nomes(api, busca="_") == ["Rifa_beneficente"]
    assert nomes(api, busca="50%") == ["Taxa 50% da rifa"]


def test_caractere_nulo_na_busca_e_ignorado(api):
    resposta = api.get("/api/categorias-despesa", params={"busca": "Vi" + chr(0) + "agens"})
    assert resposta.status_code == 200
    assert [c["nome"] for c in resposta.json()] == ["Viagens"]
    assert nomes(api, busca=chr(0)) == nomes(api)


def test_busca_e_situacao_juntas(api):
    criar(api, nome="Viagens internacionais", ativo=False)

    assert nomes(api, busca="viagens") == ["Viagens"]
    assert nomes(api, busca="viagens", situacao="inativos") == ["Viagens internacionais"]
    assert sorted(nomes(api, busca="viagens", situacao="todos")) == [
        "Viagens",
        "Viagens internacionais",
    ]


# ---------- Perfis ----------


def test_sem_login_nao_acessa_nada(sem_login):
    assert sem_login.get("/api/categorias-despesa").status_code == 401
    assert sem_login.get("/api/categorias-despesa/1").status_code == 401
    assert sem_login.post("/api/categorias-despesa", json=corpo()).status_code == 401
    assert sem_login.put("/api/categorias-despesa/1", json=corpo()).status_code == 401


def test_token_invalido_nao_acessa(sem_login):
    resposta = sem_login.get("/api/categorias-despesa", headers={"Authorization": "Bearer x"})
    assert resposta.status_code == 401


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_consultam(api, api_como, perfil):
    criada = criar(api)
    cliente = api_como(perfil)

    assert "Uniformes" in nomes(cliente)
    assert cliente.get(f"/api/categorias-despesa/{criada['id']}").status_code == 200


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.ADMINISTRADOR])
def test_operador_e_administrador_cadastram_e_editam(api_como, perfil):
    cliente = api_como(perfil)
    criada = criar(cliente)

    assert editar(cliente, criada["id"], nome="Editada").status_code == 200
    assert editar(cliente, criada["id"], nome="Editada", ativo=False).status_code == 200


def test_consulta_so_visualiza(api, api_como, db):
    criada = criar(api)
    consulta = api_como(Perfil.CONSULTA)

    assert cadastrar(consulta, nome="Invasora").status_code == 403
    assert editar(consulta, criada["id"], nome="Invadida").status_code == 403
    assert editar(consulta, criada["id"], ativo=False).status_code == 403
    nomes_gravados = no_banco(db)
    assert "Uniformes" in nomes_gravados
    assert "Invasora" not in nomes_gravados
    assert "Invadida" not in nomes_gravados


def test_o_perfil_e_conferido_antes_de_tudo(api_como):
    """A consulta não descobre se a categoria existe nem se os dados estão certos."""
    consulta = api_como(Perfil.CONSULTA)

    assert editar(consulta, 999999).status_code == 403
    assert consulta.post("/api/categorias-despesa", json={}).status_code == 403


def test_usuario_desativado_nao_acessa(api_como, db):
    cliente = api_como(Perfil.OPERADOR)
    db.execute(update(Usuario).where(Usuario.email.like("operador%")).values(ativo=False))
    db.flush()

    assert cliente.get("/api/categorias-despesa").status_code == 401


# ---------- Esquema da API ----------


def test_o_nome_consta_como_obrigatorio_no_openapi(api):
    esquema = api.get("/openapi.json").json()["components"]["schemas"]["CategoriaDespesaEntrada"]
    assert esquema["required"] == ["nome"]
