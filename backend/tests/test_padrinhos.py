import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DataError, IntegrityError

from app.models import Padrinho, Perfil, Usuario
from app.routers import padrinhos as rota_padrinhos
from app.schemas.padrinho import cnpj_e_valido, limpa_cnpj

# CNPJs válidos: dois numéricos e o exemplo alfanumérico da Receita Federal
CNPJ_A = "11222333000181"
CNPJ_B = "11444777000161"
CNPJ_ALFA = "12ABC34501DE35"


# Os campos obrigatórios de um padrinho: nome, telefone, e-mail e dia do vencimento
TELEFONE = "(31) 98888-7777"
EMAIL = "financeiro@sartori.com.br"


def corpo(**campos) -> dict:
    return {
        "nome": "Sartori Serviços",
        "telefone": TELEFONE,
        "email": EMAIL,
        "dia_vencimento": 25,
    } | campos


def cadastrar(cliente, **campos):
    return cliente.post("/api/padrinhos", json=corpo(**campos))


def criar(cliente, **campos) -> dict:
    resposta = cadastrar(cliente, **campos)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


def no_banco(db) -> list[Padrinho]:
    db.expire_all()
    return list(db.scalars(select(Padrinho).order_by(Padrinho.id)))


# ---------- Cadastrar ----------


def test_cadastra_so_com_os_campos_obrigatorios(api, db):
    """Nome, telefone, e-mail e dia do vencimento: o resto é opcional."""
    resposta = cadastrar(api)

    assert resposta.status_code == 201
    assert resposta.json() == {
        "id": resposta.json()["id"],
        "nome": "Sartori Serviços",
        "cnpj": None,
        "contato": None,
        "telefone": TELEFONE,
        "email": EMAIL,
        "dia_vencimento": 25,
        "emitir_ate_dia": None,
        "ativo": True,
        "alunos_apadrinhados": 0,
    }
    assert len(no_banco(db)) == 1


def test_cadastra_com_todos_os_dados(api):
    resposta = cadastrar(
        api,
        nome="Sartori Serviços Ltda",
        cnpj="11.222.333/0001-81",
        contato="Marcos Sartori",
        telefone="(31) 98888-7777",
        email="financeiro@sartori.com.br",
        dia_vencimento=25,
        emitir_ate_dia=10,
    )

    assert resposta.status_code == 201
    assert resposta.json() | {"id": 0} == {
        "id": 0,
        "nome": "Sartori Serviços Ltda",
        "cnpj": CNPJ_A,
        "contato": "Marcos Sartori",
        "telefone": "(31) 98888-7777",
        "email": "financeiro@sartori.com.br",
        "dia_vencimento": 25,
        "emitir_ate_dia": 10,
        "ativo": True,
        "alunos_apadrinhados": 0,
    }


def test_o_cadastro_pode_ser_consultado_depois(api):
    criado = criar(api, cnpj=CNPJ_A, contato="Marcos")
    assert api.get(f"/api/padrinhos/{criado['id']}").json() == criado


def test_limpa_espacos_do_nome_e_do_contato(api):
    padrinho = criar(api, nome="  Sartori    Serviços  ", contato="  Marcos \n  Sartori ")
    assert padrinho["nome"] == "Sartori Serviços"
    assert padrinho["contato"] == "Marcos Sartori"


@pytest.mark.parametrize("campo", ["cnpj", "contato"])
@pytest.mark.parametrize("vazio", ["", "   ", None])
def test_campo_opcional_em_branco_vira_nulo(api, campo, vazio):
    assert criar(api, **{campo: vazio})[campo] is None


def test_emitir_ate_dia_em_branco_vira_nulo(api):
    assert criar(api, emitir_ate_dia="")["emitir_ate_dia"] is None
    assert criar(api, nome="Outra Empresa", emitir_ate_dia=None)["emitir_ate_dia"] is None


def test_campos_extras_sao_ignorados(api, db):
    resposta = cadastrar(api, id=999, criado_em="2000-01-01T00:00:00", situacao="x", papel="admin")
    assert resposta.status_code == 201
    assert resposta.json()["id"] != 999
    assert no_banco(db)[0].criado_em.year >= 2026


def test_padrinhos_com_o_mesmo_nome_sao_permitidos(api):
    criar(api, nome="Empresa Igual", cnpj=CNPJ_A)
    criar(api, nome="Empresa Igual", cnpj=CNPJ_B)
    assert len(api.get("/api/padrinhos").json()) == 2


# ---------- Nome ----------


@pytest.mark.parametrize("nome", ["", " ", "a", None, 5, True, ["x"], {"a": 1}, "x" * 121])
def test_recusa_nome_invalido(api, db, nome):
    assert "nome" in erros_de(cadastrar(api, nome=nome))
    assert no_banco(db) == []


def test_limites_do_nome(api):
    assert cadastrar(api, nome="ab").status_code == 201
    assert cadastrar(api, nome="a" * 120, cnpj=CNPJ_A).status_code == 201


def test_nome_sem_o_campo_da_422(api):
    resposta = api.post("/api/padrinhos", json={"dia_vencimento": 10})
    assert "nome" in erros_de(resposta)


def test_recusa_caractere_nulo_no_texto(api):
    for campo in ("nome", "contato"):
        erros = erros_de(cadastrar(api, **{campo: "texto" + chr(0) + "nulo"}))
        assert erros[campo] == "O texto tem um caractere inválido"


# ---------- CNPJ ----------


@pytest.mark.parametrize(
    ("enviado", "guardado"),
    [
        (CNPJ_A, CNPJ_A),
        ("11.222.333/0001-81", CNPJ_A),
        ("  11.222.333/0001-81  ", CNPJ_A),
        ("11 222 333 0001 81", CNPJ_A),
        ("11222333/0001-81", CNPJ_A),
        (CNPJ_B, CNPJ_B),
        (CNPJ_ALFA, CNPJ_ALFA),
        ("12.ABC.345/01DE-35", CNPJ_ALFA),
        ("12.abc.345/01de-35", CNPJ_ALFA),
    ],
)
def test_aceita_cnpj_valido_com_ou_sem_mascara_e_guarda_so_os_14_caracteres(api, enviado, guardado):
    assert criar(api, cnpj=enviado)["cnpj"] == guardado


@pytest.mark.parametrize(
    "cnpj",
    [
        "11222333000182",  # dígito verificador errado
        "11222333000191",
        "11222333000180",
        "00000000000000",  # todos iguais passariam na conta, mas não existem
        "11111111111111",
        "99999999999999",
        "AAAAAAAAAAAAAA",
        "1122233300018",  # curto
        "112223330001811",  # comprido
        "11222333000",
        "1",
        "12ABC34501DE36",  # alfanumérico com dígito errado
        "12ABC34501DEAB",  # letras nos dígitos verificadores
        "11.222.333/0001-8!",
        "11,222,333/0001-81",
        "11_222_333_0001_81",
        "١١٢٢٢٣٣٣٠٠٠١٨١",  # dígitos de outro alfabeto
        "11222333000１81",  # dígito de largura total
        "ßßßßßßßßßßßßßß",
        "abc",
        "11222333000181" + chr(0),
    ],
)
def test_recusa_cnpj_invalido(api, db, cnpj):
    resposta = cadastrar(api, cnpj=cnpj)
    assert resposta.status_code == 422
    assert no_banco(db) == []


def test_mensagem_de_cnpj_invalido_em_portugues(api):
    assert erros_de(cadastrar(api, cnpj="11222333000182"))["cnpj"] == (
        "CNPJ inválido. Confira os números"
    )


@pytest.mark.parametrize("cnpj", [5, 11222333000181, True, ["11222333000181"], {"a": 1}])
def test_cnpj_que_nao_e_texto_e_recusado(api, cnpj):
    assert "cnpj" in erros_de(cadastrar(api, cnpj=cnpj))


def test_funcao_do_cnpj_com_os_exemplos_conhecidos():
    assert cnpj_e_valido(CNPJ_A)
    assert cnpj_e_valido(CNPJ_B)
    assert cnpj_e_valido(CNPJ_ALFA)
    assert not cnpj_e_valido("11222333000182")
    assert not cnpj_e_valido("00000000000000")
    assert limpa_cnpj(" 12.abc.345/01de-35 ") == CNPJ_ALFA


# CNPJs válidos em que o dígito verificador sai de cada tipo de resto da conta (resto 0 ou 1
# vira dígito 0; resto 2 vira 9; os demais viram 11 menos o resto)
CNPJS_POR_RESTO = [
    "62819482199300",  # 1º dígito: resto 0 | 2º dígito: resto 1
    "83417047187401",  # 1º dígito: resto 1
    "36671276842697",  # 1º dígito: resto 2
    "76018955597940",  # 2º dígito: resto 0
    "52601815908369",  # 2º dígito: resto 2 | 1º dígito: outro resto
    "01661318609164",  # 2º dígito: outro resto
]


@pytest.mark.parametrize("cnpj", CNPJS_POR_RESTO)
def test_aceita_cnpj_em_cada_caso_do_calculo_do_digito(api, cnpj):
    assert cnpj_e_valido(cnpj)
    assert criar(api, cnpj=cnpj)["cnpj"] == cnpj


@pytest.mark.parametrize(
    "cnpj", ["1122233300@140", "1122233300_105", "1122233300,194", "11222333000!77"]
)
def test_recusa_caractere_estranho_mesmo_com_os_digitos_certos(api, db, cnpj):
    """A conta dos dígitos fecha, mas só letras e números formam um CNPJ: o formato também vale."""
    assert not cnpj_e_valido(cnpj)
    assert "cnpj" in erros_de(cadastrar(api, cnpj=cnpj))
    assert no_banco(db) == []


# ---------- CNPJ repetido ----------


def test_cnpj_repetido_da_409(api, db):
    criar(api, nome="Primeira", cnpj=CNPJ_A)

    resposta = cadastrar(api, nome="Segunda", cnpj=CNPJ_A)

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe um padrinho com este CNPJ"
    assert [p.nome for p in no_banco(db)] == ["Primeira"]


@pytest.mark.parametrize(
    "outra_forma", ["11.222.333/0001-81", "11 222 333 0001 81", " 11222333000181 "]
)
def test_cnpj_repetido_com_outra_mascara_tambem_da_409(api, outra_forma):
    criar(api, cnpj=CNPJ_A)
    assert cadastrar(api, nome="Outra", cnpj=outra_forma).status_code == 409


def test_cnpj_alfanumerico_repetido_com_outra_caixa_da_409(api):
    criar(api, cnpj="12.ABC.345/01DE-35")
    assert cadastrar(api, nome="Outra", cnpj="12abc34501de35").status_code == 409


def test_varios_padrinhos_sem_cnpj_sao_permitidos(api):
    for nome in ("Sem CNPJ Um", "Sem CNPJ Dois", "Sem CNPJ Tres"):
        criar(api, nome=nome)
    assert len(api.get("/api/padrinhos").json()) == 3


def test_editar_mantendo_o_proprio_cnpj_e_permitido(api):
    criado = criar(api, cnpj=CNPJ_A)
    resposta = api.put(f"/api/padrinhos/{criado['id']}", json=corpo(cnpj=CNPJ_A, nome="Novo Nome"))
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Novo Nome"


def test_editar_para_o_cnpj_de_outro_da_409_e_nada_muda(api, db):
    criar(api, nome="Primeira", cnpj=CNPJ_A)
    segunda = criar(api, nome="Segunda", cnpj=CNPJ_B)

    resposta = api.put(f"/api/padrinhos/{segunda['id']}", json=corpo(nome="Mudou", cnpj=CNPJ_A))

    assert resposta.status_code == 409
    por_nome = {p.nome: p.cnpj for p in no_banco(db)}
    assert por_nome == {"Primeira": CNPJ_A, "Segunda": CNPJ_B}


def test_corrida_entre_dois_cadastros_do_mesmo_cnpj_vira_409_e_nao_500(api, db, monkeypatch):
    """Os dois pedidos passam pela conferência prévia: só o índice único do banco os separa."""
    criar(api, nome="Primeira", cnpj=CNPJ_A)
    monkeypatch.setattr(rota_padrinhos, "exige_cnpj_livre", lambda *args, **kwargs: None)

    resposta = cadastrar(api, nome="Segunda", cnpj=CNPJ_A)

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe um padrinho com este CNPJ"
    assert [p.nome for p in no_banco(db)] == ["Primeira"]


def test_corrida_na_edicao_tambem_vira_409(api, db, monkeypatch):
    criar(api, nome="Primeira", cnpj=CNPJ_A)
    segunda = criar(api, nome="Segunda", cnpj=CNPJ_B)
    monkeypatch.setattr(rota_padrinhos, "exige_cnpj_livre", lambda *args, **kwargs: None)

    resposta = api.put(f"/api/padrinhos/{segunda['id']}", json=corpo(nome="Segunda", cnpj=CNPJ_A))

    assert resposta.status_code == 409
    assert {p.nome: p.cnpj for p in no_banco(db)}["Segunda"] == CNPJ_B


def test_outro_erro_de_integridade_nao_e_escondido_como_409(api, monkeypatch):
    """Só o CNPJ repetido vira 409: qualquer outra violação do banco continua sendo um erro real."""

    def quebra(*args, **kwargs):
        raise IntegrityError("INSERT", {}, Exception("outra_restricao"))

    monkeypatch.setattr(rota_padrinhos.Session, "commit", quebra, raising=False)
    with pytest.raises(IntegrityError):
        cadastrar(api)


# ---------- Dia do vencimento ----------


@pytest.mark.parametrize("dia", [1, 10, 15, 25, 28])
def test_aceita_os_dias_de_1_a_28(api, dia):
    assert criar(api, dia_vencimento=dia, emitir_ate_dia=None)["dia_vencimento"] == dia


@pytest.mark.parametrize(
    "dia", [0, 29, 30, 31, -1, 100, 2**40, "abc", "", None, 10.5, True, False, [10], {"a": 1}]
)
def test_recusa_dia_do_vencimento_invalido(api, db, dia):
    assert "dia_vencimento" in erros_de(cadastrar(api, dia_vencimento=dia))
    assert no_banco(db) == []


def test_mensagem_do_dia_fora_do_calendario(api):
    assert erros_de(cadastrar(api, dia_vencimento=29))["dia_vencimento"] == "Use um dia de 1 a 28"


def test_o_dia_do_vencimento_e_obrigatorio(api):
    resposta = api.post("/api/padrinhos", json={"nome": "Sem Dia"})
    assert "dia_vencimento" in erros_de(resposta)


def test_dia_enviado_como_texto_de_numero_e_aceito(api):
    assert criar(api, dia_vencimento="12")["dia_vencimento"] == 12


# ---------- Emitir a nota até o dia ----------


@pytest.mark.parametrize(("vencimento", "emitir"), [(25, 10), (25, 1), (25, 25), (28, 28), (1, 1)])
def test_aceita_emitir_a_nota_ate_o_vencimento(api, vencimento, emitir):
    padrinho = criar(api, dia_vencimento=vencimento, emitir_ate_dia=emitir)
    assert padrinho["emitir_ate_dia"] == emitir


@pytest.mark.parametrize(("vencimento", "emitir"), [(25, 26), (10, 11), (1, 2), (28, 29)])
def test_recusa_emitir_a_nota_depois_do_vencimento(api, db, vencimento, emitir):
    erros = erros_de(cadastrar(api, dia_vencimento=vencimento, emitir_ate_dia=emitir))
    assert "emitir_ate_dia" in erros
    assert no_banco(db) == []


def test_mensagem_de_nota_depois_do_vencimento(api):
    erros = erros_de(cadastrar(api, dia_vencimento=10, emitir_ate_dia=20))
    assert erros["emitir_ate_dia"] == "A nota deve ser emitida até o dia do vencimento, no máximo"


@pytest.mark.parametrize("dia", [0, -1, 29, 100, "abc", 5.5, True, False, [1], {"a": 1}])
def test_recusa_dia_da_nota_invalido(api, dia):
    assert "emitir_ate_dia" in erros_de(cadastrar(api, emitir_ate_dia=dia))


def test_dia_da_nota_zero_nao_e_confundido_com_vazio(api, db):
    """0 não é "sem dia": é um valor inválido e tem de dar erro, não ser apagado em silêncio."""
    assert cadastrar(api, emitir_ate_dia=0).status_code == 422
    assert no_banco(db) == []


def test_dia_da_nota_vale_mesmo_com_vencimento_invalido(api):
    erros = erros_de(cadastrar(api, dia_vencimento=99, emitir_ate_dia=50))
    assert "dia_vencimento" in erros
    assert "emitir_ate_dia" in erros


# ---------- Telefone e e-mail ----------


@pytest.mark.parametrize(
    "telefone", ["(31) 98888-7777", "31988887777", "3138521234", "(31) 3852-1234"]
)
def test_aceita_telefone_com_ddd(api, telefone):
    assert criar(api, telefone=telefone)["telefone"] == telefone


@pytest.mark.parametrize("telefone", ["1234", "(31) 8888-77", "319888877770", "abc", "98888-7777"])
def test_recusa_telefone_invalido(api, telefone):
    assert erros_de(cadastrar(api, telefone=telefone))["telefone"] == (
        "Telefone deve ter DDD e 8 ou 9 dígitos"
    )


@pytest.mark.parametrize("email", ["joao@", "sem-arroba", "a@b", "@exemplo.com", "a b@exemplo.com"])
def test_recusa_email_invalido(api, email):
    assert "email" in erros_de(cadastrar(api, email=email))


MENSAGEM_OBRIGATORIA = {
    "telefone": "Informe o telefone de contato",
    "email": "Informe o e-mail de contato",
}


@pytest.mark.parametrize("campo", ["telefone", "email"])
@pytest.mark.parametrize("vazio", ["", "   ", "\n\t", None])
def test_telefone_e_email_sao_obrigatorios(api, db, campo, vazio):
    """A empresa precisa poder ser procurada: sem telefone ou sem e-mail não há cadastro."""
    erros = erros_de(cadastrar(api, **{campo: vazio}))
    assert erros[campo] == MENSAGEM_OBRIGATORIA[campo]
    assert no_banco(db) == []


@pytest.mark.parametrize("campo", ["telefone", "email"])
def test_cadastro_sem_o_campo_de_contato_da_422(api, campo):
    dados = corpo()
    del dados[campo]
    resposta = api.post("/api/padrinhos", json=dados)
    assert erros_de(resposta)[campo] == MENSAGEM_OBRIGATORIA[campo]


def test_a_documentacao_da_api_diz_que_telefone_e_email_sao_obrigatorios(api):
    """O OpenAPI (RNF12) é gerado do código: não pode esconder uma regra de obrigatoriedade."""
    esquema = api.get("/openapi.json").json()["components"]["schemas"]["PadrinhoEntrada"]
    assert set(esquema["required"]) == {"nome", "telefone", "email", "dia_vencimento"}


def test_sem_telefone_e_sem_email_os_dois_erros_vem_juntos(api):
    erros = erros_de(cadastrar(api, telefone="", email=""))
    assert set(erros) == {"telefone", "email"}


@pytest.mark.parametrize("campo", ["telefone", "email"])
@pytest.mark.parametrize("vazio", ["", "   ", None])
def test_editar_nao_deixa_apagar_o_telefone_nem_o_email(api, db, campo, vazio):
    criado = criar(api)
    resposta = api.put(f"/api/padrinhos/{criado['id']}", json=corpo(**{campo: vazio}))
    assert erros_de(resposta)[campo] == MENSAGEM_OBRIGATORIA[campo]
    antes = {"telefone": TELEFONE, "email": EMAIL}
    assert getattr(no_banco(db)[0], campo) == antes[campo]


def test_o_contato_pode_ser_trocado_na_edicao(api):
    criado = criar(api)
    resposta = api.put(
        f"/api/padrinhos/{criado['id']}",
        json=corpo(telefone="31 3852-1234", email="novo@sartori.com.br"),
    )
    assert resposta.status_code == 200
    assert resposta.json()["telefone"] == "31 3852-1234"
    assert resposta.json()["email"] == "novo@sartori.com.br"


def test_so_o_cnpj_e_a_pessoa_de_contato_continuam_opcionais(api):
    padrinho = criar(api, cnpj=None, contato=None, emitir_ate_dia=None)
    assert (padrinho["cnpj"], padrinho["contato"], padrinho["emitir_ate_dia"]) == (None, None, None)


@pytest.mark.parametrize("campo", ["telefone", "email", "contato"])
@pytest.mark.parametrize("valor", [5, True, ["a"], {"a": 1}])
def test_contato_que_nao_e_texto_e_recusado(api, campo, valor):
    assert campo in erros_de(cadastrar(api, **{campo: valor}))


def test_contato_comprido_demais_e_recusado(api):
    assert "contato" in erros_de(cadastrar(api, contato="x" * 121))
    assert cadastrar(api, contato="x" * 120).status_code == 201


# ---------- Corpo malformado ----------


@pytest.mark.parametrize("conteudo", ["{", "[]", "null", '"texto"', "123", ""])
def test_corpo_malformado_da_422(api, conteudo):
    resposta = api.post(
        "/api/padrinhos", content=conteudo, headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 422


def test_o_erro_nao_repete_o_que_foi_enviado(api):
    resposta = cadastrar(api, nome="segredo" + chr(0), cnpj="11222333000182")
    assert resposta.status_code == 422
    assert "segredo" not in resposta.text
    assert "11222333000182" not in resposta.text


# ---------- Listar, buscar e filtrar ----------


def test_lista_vazia(api):
    assert api.get("/api/padrinhos").json() == []


def test_lista_em_ordem_alfabetica(api):
    for nome in ("Zeta Ltda", "Alfa Ltda", "Mega Ltda"):
        criar(api, nome=nome)
    assert [p["nome"] for p in api.get("/api/padrinhos").json()] == [
        "Alfa Ltda",
        "Mega Ltda",
        "Zeta Ltda",
    ]


def test_mesmo_nome_sai_em_ordem_estavel(api):
    ids = [criar(api, nome="Igual", cnpj=cnpj)["id"] for cnpj in (CNPJ_A, CNPJ_B)]
    assert [p["id"] for p in api.get("/api/padrinhos").json()] == ids


def test_mesmo_nome_continua_em_ordem_estavel_depois_de_editar(api):
    """Editar muda a posição da linha no banco: sem desempate, a ordem trocaria sozinha."""
    primeiro = criar(api, nome="Igual", cnpj=CNPJ_A)
    segundo = criar(api, nome="Igual", cnpj=CNPJ_B)
    api.put(
        f"/api/padrinhos/{primeiro['id']}", json=corpo(nome="Igual", cnpj=CNPJ_A, dia_vencimento=5)
    )

    ids = [p["id"] for p in api.get("/api/padrinhos").json()]
    assert ids == [primeiro["id"], segundo["id"]]


def test_por_padrao_so_os_ativos_e_o_filtro_separa_ativos_e_inativos(api):
    ativo = criar(api, nome="Empresa Ativa")
    inativo = criar(api, nome="Empresa Inativa")
    api.put(f"/api/padrinhos/{inativo['id']}", json=corpo(nome="Empresa Inativa", ativo=False))

    def nomes(**parametros):
        return [p["nome"] for p in api.get("/api/padrinhos", params=parametros).json()]

    assert nomes() == ["Empresa Ativa"]
    assert nomes(situacao="ativos") == ["Empresa Ativa"]
    assert nomes(situacao="inativos") == ["Empresa Inativa"]
    assert nomes(situacao="todos") == ["Empresa Ativa", "Empresa Inativa"]
    assert ativo["id"] != inativo["id"]


def test_situacao_desconhecida_da_422(api):
    assert api.get("/api/padrinhos", params={"situacao": "quase"}).status_code == 422


def test_busca_por_nome_sem_diferenciar_maiusculas_nem_pegar_so_o_comeco(api):
    criar(api, nome="Sartori Serviços")
    criar(api, nome="Outra Empresa")
    achados = [p["nome"] for p in api.get("/api/padrinhos", params={"busca": "ARTORI"}).json()]
    assert achados == ["Sartori Serviços"]


def test_busca_tambem_procura_no_contato(api):
    criar(api, nome="Empresa Um", contato="Marcos Sartori")
    criar(api, nome="Empresa Dois", contato="Ana Lima")
    achados = [p["nome"] for p in api.get("/api/padrinhos", params={"busca": "marcos"}).json()]
    assert achados == ["Empresa Um"]


def test_busca_sem_resultado(api):
    criar(api)
    assert api.get("/api/padrinhos", params={"busca": "inexistente"}).json() == []


def test_busca_com_curingas_do_sql_vale_como_texto(api):
    criar(api, nome="Empresa 100% Boa")
    criar(api, nome="Empresa Qualquer")
    criar(api, nome="Empresa_Com_Sublinhado")

    def busca(termo):
        return [p["nome"] for p in api.get("/api/padrinhos", params={"busca": termo}).json()]

    assert busca("%") == ["Empresa 100% Boa"]
    assert busca("_") == ["Empresa_Com_Sublinhado"]
    assert busca("100%") == ["Empresa 100% Boa"]


@pytest.mark.parametrize("busca", ["", "   ", chr(0), "a" + chr(0) + "b"])
def test_busca_em_branco_ou_com_caractere_nulo_nao_quebra(api, busca):
    criar(api)
    assert api.get("/api/padrinhos", params={"busca": busca}).status_code == 200


def test_busca_com_injecao_de_sql_nao_quebra_nem_apaga(api, db):
    criar(api)
    resposta = api.get("/api/padrinhos", params={"busca": "'; DROP TABLE padrinhos;--"})
    assert resposta.status_code == 200
    assert resposta.json() == []
    assert len(no_banco(db)) == 1


def test_busca_com_texto_enorme_nao_quebra(api):
    assert api.get("/api/padrinhos", params={"busca": "a" * 5000}).status_code == 200


def test_busca_combina_com_o_filtro_de_situacao(api):
    inativo = criar(api, nome="Sartori Antiga")
    criar(api, nome="Sartori Atual", cnpj=CNPJ_A)
    api.put(f"/api/padrinhos/{inativo['id']}", json=corpo(nome="Sartori Antiga", ativo=False))

    def nomes(situacao):
        resposta = api.get("/api/padrinhos", params={"busca": "sartori", "situacao": situacao})
        return [p["nome"] for p in resposta.json()]

    assert nomes("ativos") == ["Sartori Atual"]
    assert nomes("inativos") == ["Sartori Antiga"]


# ---------- Editar, inativar e reativar ----------


def test_edita_todos_os_campos(api):
    criado = criar(api, cnpj=CNPJ_A, contato="Marcos", telefone="31988887777")

    resposta = api.put(
        f"/api/padrinhos/{criado['id']}",
        json={
            "nome": "Sartori Novo Nome",
            "cnpj": "",
            "contato": "Ana",
            "telefone": "(31) 3852-1234",
            "email": "ana@sartori.com.br",
            "dia_vencimento": 5,
            "emitir_ate_dia": 3,
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": criado["id"],
        "nome": "Sartori Novo Nome",
        "cnpj": None,
        "contato": "Ana",
        "telefone": "(31) 3852-1234",
        "email": "ana@sartori.com.br",
        "dia_vencimento": 5,
        "emitir_ate_dia": 3,
        "ativo": True,
        "alunos_apadrinhados": 0,
    }
    assert api.get(f"/api/padrinhos/{criado['id']}").json() == resposta.json()


def test_editar_nao_muda_o_id_nem_aceita_campos_extras(api):
    criado = criar(api)
    resposta = api.put(f"/api/padrinhos/{criado['id']}", json=corpo(id=999, criado_em="2000-01-01"))
    assert resposta.json()["id"] == criado["id"]


def test_editar_atualiza_a_hora_da_alteracao(api, db):
    criado = criar(api)
    antes = no_banco(db)[0].atualizado_em
    api.put(f"/api/padrinhos/{criado['id']}", json=corpo(nome="Mudou"))
    assert no_banco(db)[0].atualizado_em >= antes


def test_inativa_e_reativa_sem_apagar(api, db):
    criado = criar(api)
    url = f"/api/padrinhos/{criado['id']}"

    assert api.put(url, json=corpo(ativo=False)).json()["ativo"] is False
    assert api.get(url).json()["ativo"] is False
    assert len(no_banco(db)) == 1

    assert api.put(url, json=corpo(ativo=True)).json()["ativo"] is True


@pytest.mark.parametrize("ativo", [0, 1, "false", "true", "no", "sim", "", None, [], {}, 2, 0.0])
def test_ativo_so_aceita_verdadeiro_ou_falso(api, db, ativo):
    """Um 0, um "no" ou um vazio não podem inativar (ou reativar) o padrinho por engano."""
    criado = criar(api)
    resposta = api.put(f"/api/padrinhos/{criado['id']}", json=corpo(ativo=ativo))
    assert erros_de(resposta)["ativo"] == "Informe verdadeiro ou falso"
    assert no_banco(db)[0].ativo is True


def test_ativo_tambem_e_estrito_no_cadastro(api, db):
    assert "ativo" in erros_de(cadastrar(api, ativo=0))
    assert no_banco(db) == []
    assert cadastrar(api, ativo=False).json()["ativo"] is False


def test_padrinho_inativo_pode_ser_editado(api):
    criado = criar(api)
    url = f"/api/padrinhos/{criado['id']}"
    api.put(url, json=corpo(ativo=False))
    resposta = api.put(url, json=corpo(nome="Novo Nome", ativo=False))
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Novo Nome"


def test_edicao_invalida_nao_muda_nada(api, db):
    criado = criar(api, cnpj=CNPJ_A)
    resposta = api.put(
        f"/api/padrinhos/{criado['id']}", json=corpo(nome="Mudou", cnpj="11222333000182")
    )
    assert resposta.status_code == 422
    assert no_banco(db)[0].nome == "Sartori Serviços"


def test_editar_exige_todos_os_campos_obrigatorios(api):
    criado = criar(api)
    resposta = api.put(f"/api/padrinhos/{criado['id']}", json={"nome": "Só o nome"})
    assert "dia_vencimento" in erros_de(resposta)


# ---------- Ids fora do normal e métodos ----------


def test_padrinho_inexistente_da_404(api):
    for resposta in (
        api.get("/api/padrinhos/999999"),
        api.put("/api/padrinhos/999999", json=corpo()),
    ):
        assert resposta.status_code == 404
        assert resposta.json()["detail"] == "Padrinho não encontrado"


@pytest.mark.parametrize("id_", [0, -1, 2_147_483_648, 99999999999999999999, "abc", "1.5"])
def test_id_fora_do_normal_da_422_e_nao_500(api, id_):
    assert api.get(f"/api/padrinhos/{id_}").status_code == 422
    assert api.put(f"/api/padrinhos/{id_}", json=corpo()).status_code == 422


def test_o_maior_id_possivel_da_404(api):
    assert api.get("/api/padrinhos/2147483647").status_code == 404


def test_padrinho_nao_pode_ser_apagado(api):
    """Nada é apagado (RN04, RN12): não existe rota de exclusão."""
    criado = criar(api)
    for metodo in ("delete", "patch"):
        resposta = getattr(api, metodo)(f"/api/padrinhos/{criado['id']}")
        assert resposta.status_code == 405
    assert api.delete("/api/padrinhos").status_code == 405
    assert api.get(f"/api/padrinhos/{criado['id']}").status_code == 200


# ---------- Perfis (RN13) ----------


def test_sem_login_nao_acessa_nada(sem_login):
    assert sem_login.get("/api/padrinhos").status_code == 401
    assert sem_login.get("/api/padrinhos/1").status_code == 401
    assert sem_login.post("/api/padrinhos", json=corpo()).status_code == 401
    assert sem_login.put("/api/padrinhos/1", json=corpo()).status_code == 401


def test_token_invalido_nao_acessa(sem_login):
    resposta = sem_login.get("/api/padrinhos", headers={"Authorization": "Bearer invalido"})
    assert resposta.status_code == 401


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_consultam(api, api_como, perfil):
    criado = criar(api)
    cliente = api_como(perfil)
    assert [p["id"] for p in cliente.get("/api/padrinhos").json()] == [criado["id"]]
    assert cliente.get(f"/api/padrinhos/{criado['id']}").status_code == 200


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.ADMINISTRADOR])
def test_operador_e_administrador_cadastram_e_editam(api_como, perfil):
    cliente = api_como(perfil)
    criado = criar(cliente)
    assert (
        cliente.put(f"/api/padrinhos/{criado['id']}", json=corpo(nome="Editado")).status_code == 200
    )


def test_consulta_so_visualiza(api, api_como, db):
    criado = criar(api)
    consulta = api_como(Perfil.CONSULTA)

    assert cadastrar(consulta).status_code == 403
    assert (
        consulta.put(f"/api/padrinhos/{criado['id']}", json=corpo(nome="Invadido")).status_code
        == 403
    )
    assert [p.nome for p in no_banco(db)] == ["Sartori Serviços"]


def test_o_perfil_e_conferido_antes_de_tudo(api_como):
    """A consulta não descobre se o padrinho existe nem se os dados estão certos."""
    consulta = api_como(Perfil.CONSULTA)
    assert consulta.put("/api/padrinhos/999999", json=corpo()).status_code == 403
    assert consulta.post("/api/padrinhos", json={}).status_code == 403


def test_usuario_desativado_nao_acessa(api, api_como, db):
    cliente = api_como(Perfil.OPERADOR)
    db.execute(update(Usuario).where(Usuario.email.like("operador%")).values(ativo=False))
    db.flush()
    assert cliente.get("/api/padrinhos").status_code == 401


# ---------- A resposta traz só o necessário ----------


def test_resposta_traz_so_os_campos_previstos(api):
    padrinho = criar(api, cnpj=CNPJ_A, contato="Marcos", telefone="31988887777")
    assert set(padrinho) == {
        "id",
        "nome",
        "cnpj",
        "contato",
        "telefone",
        "email",
        "dia_vencimento",
        "emitir_ate_dia",
        "ativo",
        "alunos_apadrinhados",
    }
    assert "criado_em" not in padrinho
    assert "atualizado_em" not in padrinho


# ---------- Regras garantidas pelo banco ----------


def novo(db, **campos) -> Padrinho:
    dados = {
        "nome": "Direto no Banco",
        "telefone": TELEFONE,
        "email": EMAIL,
        "dia_vencimento": 10,
    } | campos
    padrinho = Padrinho(**dados)
    db.add(padrinho)
    return padrinho


@pytest.mark.parametrize("dia", [0, 29, -5])
def test_banco_recusa_dia_do_vencimento_fora_de_1_a_28(db, dia):
    novo(db, dia_vencimento=dia)
    with pytest.raises(IntegrityError, match="dia_vencimento_de_1_a_28"):
        db.flush()


@pytest.mark.parametrize(("vencimento", "emitir"), [(10, 11), (10, 0), (10, 29), (28, 29)])
def test_banco_recusa_dia_da_nota_invalido(db, vencimento, emitir):
    novo(db, dia_vencimento=vencimento, emitir_ate_dia=emitir)
    with pytest.raises(IntegrityError, match="emitir_ate_dia_valido"):
        db.flush()


@pytest.mark.parametrize(
    "cnpj", ["123", "11222333000181X", "1122233300018a", "11.222.333/0001-81", "ABCDEFGHIJKLMN"]
)
def test_banco_recusa_cnpj_fora_do_formato(db, cnpj):
    novo(db, cnpj=cnpj)
    with pytest.raises((IntegrityError, DataError)):
        db.flush()


def test_banco_recusa_cnpj_repetido(db):
    novo(db, cnpj=CNPJ_A)
    db.flush()
    novo(db, nome="Outra", cnpj=CNPJ_A)
    with pytest.raises(IntegrityError, match="uq_padrinhos_cnpj"):
        db.flush()


def test_banco_aceita_varios_sem_cnpj(db):
    novo(db)
    novo(db, nome="Outra")
    db.flush()
    assert db.scalar(select(func.count()).select_from(Padrinho)) == 2


@pytest.mark.parametrize("faltando", ["nome", "telefone", "email", "dia_vencimento"])
def test_banco_recusa_campo_obrigatorio_nulo(db, faltando):
    dados = {"nome": "Sem Algo", "telefone": TELEFONE, "email": EMAIL, "dia_vencimento": 10}
    del dados[faltando]
    db.add(Padrinho(**dados))
    with pytest.raises(IntegrityError, match=faltando):
        db.flush()


def test_banco_comeca_ativo_por_padrao(db):
    db.execute(
        text(
            "INSERT INTO padrinhos (nome, telefone, email, dia_vencimento)"
            " VALUES ('Direto', '31988887777', 'a@b.com', 10)"
        )
    )
    assert db.scalar(select(Padrinho.ativo)) is True
