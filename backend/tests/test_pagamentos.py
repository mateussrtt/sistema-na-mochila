from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from app.core import tempo
from app.db.session import engine
from app.models import FormaDePagamento, Mensalidade, Pagamento, Perfil, StatusMensalidade

HOJE = date(2026, 11, 5)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Todos os testes rodam "em 5 de novembro de 2026", para não dependerem do dia em que rodam."""
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)


@pytest.fixture
def mensalidade(api, matricula) -> dict:
    """Uma mensalidade pendente de novembro de 2026, de R$ 150,00 (vence em 10/11)."""
    matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    return api.get("/api/mensalidades", params={"mes": "2026-11"}).json()[0]


def pagar(cliente, alvo, **campos):
    dados = {"data_pagamento": "2026-11-05", "valor_pago": "150.00", "forma_pagamento": "pix"}
    return cliente.post(f"/api/mensalidades/{alvo}/pagamento", json=dados | campos)


def erros_de(resposta) -> dict[str, str]:
    """Mensagens de erro de uma resposta 422, por nome do campo."""
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


def pagamentos_no_banco(db) -> list[Pagamento]:
    return list(db.scalars(select(Pagamento).order_by(Pagamento.id)))


# ---------- Registrar o pagamento ----------


def test_registra_o_pagamento_e_a_mensalidade_fica_paga(api, db, mensalidade):
    resposta = pagar(api, mensalidade["id"])

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["id"] == mensalidade["id"]
    assert corpo["status"] == "paga"
    assert corpo["situacao"] == "paga"
    assert corpo["dias_em_atraso"] == 0
    assert corpo["valor"] == "150.00"
    pagamento = corpo["pagamento"]
    assert pagamento["data_pagamento"] == "2026-11-05"
    assert pagamento["valor_pago"] == "150.00"
    assert pagamento["forma_pagamento"] == "pix"
    assert pagamento["observacao"] is None
    assert db.scalars(select(Mensalidade)).one().status == StatusMensalidade.PAGA


def test_a_lista_mostra_o_pagamento_da_mensalidade_paga(api, mensalidade):
    pagar(api, mensalidade["id"], forma_pagamento="boleto")

    paga = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()[0]
    assert paga["situacao"] == "paga"
    assert paga["pagamento"]["forma_pagamento"] == "boleto"
    assert paga["pagamento"]["valor_pago"] == "150.00"


def test_so_a_mensalidade_paga_tem_pagamento_na_lista(api, matricula):
    matricula("Ana Paga")
    matricula("Beto Pendente")
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    lista = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    pagar(api, lista[0]["id"])

    lista = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    por_nome = {m["aluno"]["nome"]: m for m in lista}
    assert por_nome["Ana Paga"]["pagamento"] is not None
    assert por_nome["Beto Pendente"]["pagamento"] is None
    assert por_nome["Beto Pendente"]["situacao"] == "a_vencer"


def test_guarda_quem_registrou_e_quando(api_como, db, mensalidade):
    operador = api_como(Perfil.OPERADOR)
    quem_e = operador.get("/api/auth/eu").json()

    resposta = pagar(operador, mensalidade["id"])

    pagamento = pagamentos_no_banco(db)[0]
    assert pagamento.criado_por_id == quem_e["id"]
    assert pagamento.criado_em is not None
    assert pagamento.cancelado_em is None
    assert resposta.json()["pagamento"]["registrado_por"] == quem_e["nome"]
    # A hora do registro vem do banco (o relógio real), não da data do pagamento
    assert resposta.json()["pagamento"]["registrado_em"].startswith(str(date.today().year))


def test_a_lista_diz_quem_registrou(api_como, api, mensalidade):
    operador = api_como(Perfil.OPERADOR)
    pagar(operador, mensalidade["id"])
    nome = operador.get("/api/auth/eu").json()["nome"]

    paga = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()[0]
    assert paga["pagamento"]["registrado_por"] == nome


def test_a_lista_mostra_so_o_pagamento_ativo(api, db, mensalidade):
    """Um pagamento cancelado (RF17, no futuro) não conta: vale o que está ativo."""
    usuario_id = db.scalars(select(Mensalidade.criado_por_id)).first()
    cancelado = Pagamento(
        mensalidade_id=mensalidade["id"],
        data_pagamento=date(2026, 11, 1),
        valor_pago=Decimal("100.00"),
        forma_pagamento=FormaDePagamento.DINHEIRO,
        criado_por_id=usuario_id,
        cancelado_em=func.now(),
    )
    ativo = Pagamento(
        mensalidade_id=mensalidade["id"],
        data_pagamento=date(2026, 11, 2),
        valor_pago=Decimal("150.00"),
        forma_pagamento=FormaDePagamento.PIX,
        criado_por_id=usuario_id,
    )
    db.add_all([ativo, cancelado])
    db.scalars(select(Mensalidade)).one().status = StatusMensalidade.PAGA
    db.flush()

    paga = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()[0]
    assert paga["pagamento"]["forma_pagamento"] == "pix"
    assert paga["pagamento"]["data_pagamento"] == "2026-11-02"


def test_resposta_do_pagamento_traz_so_o_necessario(api, mensalidade):
    corpo = pagar(api, mensalidade["id"]).json()
    assert set(corpo["pagamento"]) == {
        "data_pagamento",
        "valor_pago",
        "forma_pagamento",
        "observacao",
        "registrado_por",
        "registrado_em",
    }
    assert "31977776666" not in str(corpo)  # telefone do responsável
    assert "senha" not in str(corpo).lower()


@pytest.mark.parametrize("forma", ["pix", "dinheiro", "boleto", "outra"])
def test_aceita_as_quatro_formas_de_pagamento(api, mensalidade, forma):
    resposta = pagar(api, mensalidade["id"], forma_pagamento=forma)
    assert resposta.status_code == 201
    assert resposta.json()["pagamento"]["forma_pagamento"] == forma


@pytest.mark.parametrize(
    "forma", ["cartao", "PIX", "Pix", "", " pix", None, 5, ["pix"], {"pix": 1}, True]
)
def test_recusa_forma_de_pagamento_desconhecida(api, db, mensalidade, forma):
    erros = erros_de(pagar(api, mensalidade["id"], forma_pagamento=forma))
    assert "forma_pagamento" in erros
    assert "PIX, dinheiro, boleto ou outra" in erros["forma_pagamento"]
    assert pagamentos_no_banco(db) == []


def test_recusa_pagamento_sem_a_forma(api, mensalidade):
    resposta = api.post(
        f"/api/mensalidades/{mensalidade['id']}/pagamento",
        json={"data_pagamento": "2026-11-05", "valor_pago": "150.00"},
    )
    assert "forma_pagamento" in erros_de(resposta)


# ---------- Data do pagamento (RN09) ----------


def test_aceita_pagamento_de_hoje(api, mensalidade):
    assert pagar(api, mensalidade["id"], data_pagamento="2026-11-05").status_code == 201


def test_recusa_pagamento_no_futuro(api, db, mensalidade):
    erros = erros_de(pagar(api, mensalidade["id"], data_pagamento="2026-11-06"))
    assert erros["data_pagamento"] == "A data do pagamento não pode ser no futuro"
    assert pagamentos_no_banco(db) == []
    assert db.scalars(select(Mensalidade)).one().status == StatusMensalidade.PENDENTE


@pytest.mark.parametrize("data", ["2026-12-31", "2099-01-01", "9999-12-31"])
def test_recusa_datas_bem_adiante(api, mensalidade, data):
    assert "data_pagamento" in erros_de(pagar(api, mensalidade["id"], data_pagamento=data))


def test_aceita_pagamento_de_dias_atras_e_depois_do_vencimento(api, matricula):
    matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-10"})
    outubro = api.get("/api/mensalidades", params={"mes": "2026-10"}).json()[0]
    assert outubro["situacao"] == "atrasada"

    resposta = pagar(api, outubro["id"], data_pagamento="2026-11-01")

    assert resposta.status_code == 201
    assert resposta.json()["situacao"] == "paga"
    assert resposta.json()["dias_em_atraso"] == 0


def test_aceita_pagamento_antes_do_mes_da_mensalidade(api, matricula):
    """Quem adianta o pagamento de dezembro em novembro: o dinheiro entrou antes."""
    matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-12"})
    dezembro = api.get("/api/mensalidades", params={"mes": "2026-12"}).json()[0]
    assert pagar(api, dezembro["id"], data_pagamento="2026-11-05").status_code == 201


def test_limites_da_data_mais_antiga(api, matricula):
    matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    id_ = api.get("/api/mensalidades").json()[0]["id"]
    erros = erros_de(pagar(api, id_, data_pagamento="1999-12-31"))
    assert erros["data_pagamento"] == "Essa data é antiga demais"
    assert pagar(api, id_, data_pagamento="2000-01-01").status_code == 201


@pytest.mark.parametrize(
    "data", ["", "   ", None, "ontem", "2026-13-01", "2026-02-30", "05/11/2026", 20261105]
)
def test_recusa_data_vazia_ou_invalida(api, db, mensalidade, data):
    erros = erros_de(pagar(api, mensalidade["id"], data_pagamento=data))
    assert "data_pagamento" in erros
    assert pagamentos_no_banco(db) == []


def test_pede_a_data_quando_ela_nao_vem(api, mensalidade):
    resposta = api.post(
        f"/api/mensalidades/{mensalidade['id']}/pagamento",
        json={"valor_pago": "150.00", "forma_pagamento": "pix"},
    )
    assert "data_pagamento" in erros_de(resposta)


def test_mensagem_de_data_vazia_e_em_portugues(api, mensalidade):
    erros = erros_de(pagar(api, mensalidade["id"], data_pagamento=""))
    assert erros["data_pagamento"] == "Informe a data do pagamento"


# ---------- Valor pago (RN09, RNF08) ----------


@pytest.mark.parametrize(
    "valor",
    [
        "0",
        "0.00",
        "0,00",
        "-1",
        "-150.00",
        "abc",
        "",
        "   ",
        "NaN",
        "nan",
        "Infinity",
        "-Infinity",
        "1e400",
        "0.001",
        "150.005",
        "1e-400",
        "100000000",
        "100000000.00",
        "99999999999999999999",
        "R$ 150,00",
        "1.500,00",
        "150 reais",
        None,
        [],
        {},
        True,
        0,
        -5,
    ],
)
def test_recusa_valor_invalido(api, db, mensalidade, valor):
    erros = erros_de(pagar(api, mensalidade["id"], valor_pago=valor))
    assert "valor_pago" in erros
    assert pagamentos_no_banco(db) == []
    assert db.scalars(select(Mensalidade)).one().status == StatusMensalidade.PENDENTE


@pytest.mark.parametrize("valor", ["NaN", "nan", "Infinity", "-Infinity", "inf"])
def test_nan_e_infinito_tem_mensagem_em_portugues(api, mensalidade, valor):
    """O pydantic já recusaria, mas em inglês: a checagem própria dá a mensagem certa."""
    erros = erros_de(pagar(api, mensalidade["id"], valor_pago=valor))
    assert erros["valor_pago"] == "Informe um valor válido"


def test_mensagens_de_valor_sao_em_portugues(api, mensalidade):
    id_ = mensalidade["id"]
    assert erros_de(pagar(api, id_, valor_pago="0"))["valor_pago"] == (
        "O valor pago deve ser maior que zero"
    )
    assert erros_de(pagar(api, id_, valor_pago="abc"))["valor_pago"] == "Informe um valor válido"
    assert erros_de(pagar(api, id_, valor_pago=""))["valor_pago"] == "Informe o valor pago"
    assert erros_de(pagar(api, id_, valor_pago="1.234"))["valor_pago"] == (
        "Use no máximo 2 casas decimais"
    )
    assert erros_de(pagar(api, id_, valor_pago="100000000"))["valor_pago"] == (
        "O valor pago é alto demais"
    )


@pytest.mark.parametrize("valor", ["150", "150.0", "150,00", " 150.00 ", 150, 150.0])
def test_aceita_o_valor_igual_ao_previsto_em_varios_formatos(api, mensalidade, valor):
    resposta = pagar(api, mensalidade["id"], valor_pago=valor)
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["pagamento"]["valor_pago"] == "150.00"


def test_valor_menor_e_o_maior_valor_possivel_com_observacao(api, matricula):
    matricula(valor_mensalidade="10.00")
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    id_ = api.get("/api/mensalidades").json()[0]["id"]
    resposta = pagar(api, id_, valor_pago="99999999.99", observacao="Pagou o ano todo junto")
    assert resposta.status_code == 201
    assert resposta.json()["pagamento"]["valor_pago"] == "99999999.99"


def test_valor_pequeno_com_observacao(api, matricula):
    matricula(valor_mensalidade="10.00")
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    id_ = api.get("/api/mensalidades").json()[0]["id"]
    resposta = pagar(api, id_, valor_pago="0.01", observacao="Só um pedaço")
    assert resposta.status_code == 201
    assert resposta.json()["pagamento"]["valor_pago"] == "0.01"


def test_valor_e_guardado_com_duas_casas_exatas(api, db, mensalidade):
    pagar(api, mensalidade["id"], valor_pago="150.5", observacao="Faltou 50 centavos")
    assert pagamentos_no_banco(db)[0].valor_pago == Decimal("150.50")


# ---------- Valor diferente do previsto e observação (UC07) ----------


def test_valor_diferente_sem_observacao_pede_o_motivo(api, db, mensalidade):
    resposta = pagar(api, mensalidade["id"], valor_pago="120.00")
    erros = erros_de(resposta)
    assert erros["observacao"] == (
        "O valor é diferente do previsto (R$ 150,00). Explique o motivo na observação"
    )
    assert pagamentos_no_banco(db) == []
    assert db.scalars(select(Mensalidade)).one().status == StatusMensalidade.PENDENTE


@pytest.mark.parametrize("valor", ["120.00", "150.01", "149.99", "300", "0.01"])
def test_qualquer_diferenca_de_valor_exige_observacao(api, mensalidade, valor):
    assert "observacao" in erros_de(pagar(api, mensalidade["id"], valor_pago=valor))


@pytest.mark.parametrize("observacao", ["", "   ", None])
def test_observacao_em_branco_nao_vale_como_motivo(api, mensalidade, observacao):
    resposta = pagar(api, mensalidade["id"], valor_pago="120.00", observacao=observacao)
    assert "observacao" in erros_de(resposta)


def test_valor_diferente_com_observacao_e_registrado(api, db, mensalidade):
    resposta = pagar(
        api, mensalidade["id"], valor_pago="120.00", observacao="  Combinado com a mãe  "
    )
    assert resposta.status_code == 201
    assert resposta.json()["pagamento"]["observacao"] == "Combinado com a mãe"
    assert resposta.json()["pagamento"]["valor_pago"] == "120.00"
    # O valor da mensalidade não muda: só o que foi pago é registrado
    assert resposta.json()["valor"] == "150.00"
    assert pagamentos_no_banco(db)[0].observacao == "Combinado com a mãe"


def test_observacao_e_opcional_quando_o_valor_e_o_previsto(api, db, mensalidade):
    resposta = pagar(api, mensalidade["id"], observacao="   ")
    assert resposta.status_code == 201
    assert resposta.json()["pagamento"]["observacao"] is None
    assert pagamentos_no_banco(db)[0].observacao is None


def test_observacao_aceita_acentos_e_emoji(api, mensalidade):
    texto = "Pagou em mãos — João 🙂 (R$ 150)"
    resposta = pagar(api, mensalidade["id"], observacao=texto)
    assert resposta.json()["pagamento"]["observacao"] == texto


def test_limites_da_observacao(api, matricula):
    matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    id_ = api.get("/api/mensalidades").json()[0]["id"]

    erros = erros_de(pagar(api, id_, observacao="a" * 256))
    assert erros["observacao"] == "Use no máximo 255 caracteres na observação"
    # Espaços nas pontas não contam: o texto que sobra tem 255
    resposta = pagar(api, id_, observacao="  " + "a" * 255 + "  ")
    assert resposta.status_code == 201
    assert resposta.json()["pagamento"]["observacao"] == "a" * 255


def test_recusa_observacao_com_caractere_nulo(api, db, mensalidade):
    erros = erros_de(pagar(api, mensalidade["id"], observacao="texto" + chr(0) + "nulo"))
    assert erros["observacao"] == "O texto tem um caractere inválido"
    assert pagamentos_no_banco(db) == []


@pytest.mark.parametrize("observacao", [5, ["a"], {"a": 1}, True])
def test_recusa_observacao_que_nao_e_texto(api, mensalidade, observacao):
    assert "observacao" in erros_de(pagar(api, mensalidade["id"], observacao=observacao))


# ---------- Uma mensalidade só aceita um pagamento (RF10) ----------


def test_nao_aceita_segundo_pagamento(api, db, mensalidade):
    pagar(api, mensalidade["id"])

    resposta = pagar(api, mensalidade["id"], valor_pago="150.00", forma_pagamento="dinheiro")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Esta mensalidade já foi paga"
    assert len(pagamentos_no_banco(db)) == 1
    assert pagamentos_no_banco(db)[0].forma_pagamento == FormaDePagamento.PIX


def test_um_pagamento_recusado_nao_altera_o_primeiro(api, mensalidade):
    pagar(api, mensalidade["id"], data_pagamento="2026-11-02", forma_pagamento="boleto")
    pagar(api, mensalidade["id"], data_pagamento="2026-11-04", forma_pagamento="pix")
    paga = api.get("/api/mensalidades").json()[0]
    assert paga["pagamento"]["data_pagamento"] == "2026-11-02"
    assert paga["pagamento"]["forma_pagamento"] == "boleto"


@pytest.mark.parametrize(
    ("status", "mensagem"),
    [
        (StatusMensalidade.ISENTA, "Uma mensalidade isenta não recebe pagamento"),
        (StatusMensalidade.CANCELADA, "Uma mensalidade cancelada não recebe pagamento"),
    ],
)
def test_isenta_e_cancelada_nao_recebem_pagamento(api, db, mensalidade, status, mensagem):
    acao = "isentar" if status == StatusMensalidade.ISENTA else "cancelar"
    alteracao = api.patch(
        f"/api/mensalidades/{mensalidade['id']}/{acao}", json={"motivo": "Motivo de teste"}
    )
    assert alteracao.status_code == 200

    resposta = pagar(api, mensalidade["id"])

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == mensagem
    assert pagamentos_no_banco(db) == []
    assert db.scalars(select(Mensalidade)).one().status == status


def test_pagamento_invalido_em_mensalidade_ja_paga_diz_que_ja_foi_paga(api, mensalidade):
    """O estado da mensalidade é conferido antes do conteúdo do pagamento."""
    pagar(api, mensalidade["id"])
    assert pagar(api, mensalidade["id"], valor_pago="120.00").status_code == 409


def test_paga_sai_da_lista_de_atrasadas_e_a_vencer(api, monkeypatch, mensalidade):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 20))
    antes = api.get("/api/mensalidades", params={"situacao": "atrasada"}).json()
    assert [m["id"] for m in antes] == [mensalidade["id"]]

    pagar(api, mensalidade["id"], data_pagamento="2026-11-20")

    assert api.get("/api/mensalidades", params={"situacao": "atrasada"}).json() == []
    assert api.get("/api/mensalidades", params={"situacao": "a_vencer"}).json() == []
    pagas = api.get("/api/mensalidades", params={"situacao": "paga"}).json()
    assert [m["id"] for m in pagas] == [mensalidade["id"]]
    assert pagas[0]["dias_em_atraso"] == 0


def test_mensalidade_de_matricula_encerrada_ainda_pode_ser_paga(api, matricula):
    """Quem saiu continua devendo o que já foi cobrado: o histórico não se perde."""
    criada = matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    api.patch(f"/api/matriculas/{criada['id']}/encerrar", json={"data_encerramento": "2026-11-03"})
    id_ = api.get("/api/mensalidades").json()[0]["id"]
    assert pagar(api, id_).status_code == 201


def test_pagamento_de_mensalidade_com_bolsa_parcial(api, matricula):
    matricula(bolsa="parcial", valor_mensalidade="80.00")
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    mensalidade = api.get("/api/mensalidades").json()[0]
    resposta = pagar(api, mensalidade["id"], valor_pago="80.00")
    assert resposta.status_code == 201
    assert resposta.json()["bolsa"] == "parcial"


# ---------- Mensalidade inexistente e ids fora do normal ----------


def test_mensalidade_inexistente_da_404(api, db):
    resposta = pagar(api, 999999)
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Mensalidade não encontrada"
    assert pagamentos_no_banco(db) == []


@pytest.mark.parametrize("id_", [0, -1, 2_147_483_648, 99999999999999999999, "abc", "1.5"])
def test_id_fora_do_normal_da_422_e_nao_500(api, id_):
    assert pagar(api, id_).status_code == 422


def test_o_maior_id_possivel_da_404(api):
    assert pagar(api, 2_147_483_647).status_code == 404


def test_corpo_malformado_da_422(api, mensalidade):
    url = f"/api/mensalidades/{mensalidade['id']}/pagamento"
    for corpo in ("{", "[]", "null", '"texto"', "123", ""):
        resposta = api.post(url, content=corpo, headers={"Content-Type": "application/json"})
        assert resposta.status_code == 422, (corpo, resposta.text)


def test_corpo_vazio_da_422_com_os_tres_campos(api, mensalidade):
    resposta = api.post(f"/api/mensalidades/{mensalidade['id']}/pagamento", json={})
    assert set(erros_de(resposta)) == {"data_pagamento", "valor_pago", "forma_pagamento"}


def test_erro_nao_repete_o_que_foi_enviado(api, mensalidade):
    resposta = pagar(api, mensalidade["id"], observacao="segredo" + chr(0), valor_pago="abc")
    assert "segredo" not in resposta.text
    assert "abc" not in resposta.text


def test_campos_extras_sao_ignorados(api, db, mensalidade):
    resposta = pagar(
        api,
        mensalidade["id"],
        status="isenta",
        criado_por_id=999,
        criado_em="2000-01-01T00:00:00",
        mensalidade_id=123,
        cancelado_em="2026-11-01T00:00:00",
        id=77,
    )
    assert resposta.status_code == 201
    pagamento = pagamentos_no_banco(db)[0]
    assert pagamento.mensalidade_id == mensalidade["id"]
    assert pagamento.criado_por_id != 999
    assert pagamento.cancelado_em is None
    assert pagamento.criado_em.year >= 2026
    assert resposta.json()["status"] == "paga"


# ---------- Permissões (RN13, RF02) ----------


def test_sem_login_nao_registra_nem_lista(sem_login):
    assert sem_login.post("/api/mensalidades/1/pagamento", json={}).status_code == 401


def test_consulta_nao_registra_pagamento(api_como, db, mensalidade):
    resposta = pagar(api_como(Perfil.CONSULTA), mensalidade["id"])
    assert resposta.status_code == 403
    assert pagamentos_no_banco(db) == []
    assert db.scalars(select(Mensalidade)).one().status == StatusMensalidade.PENDENTE


def test_consulta_nao_descobre_se_a_mensalidade_existe(api_como):
    """O perfil é conferido antes de procurar a mensalidade."""
    assert pagar(api_como(Perfil.CONSULTA), 999999).status_code == 403


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.ADMINISTRADOR])
def test_operador_e_administrador_registram(api_como, mensalidade, perfil):
    assert pagar(api_como(perfil), mensalidade["id"]).status_code == 201


def test_consulta_ve_o_pagamento_na_lista(api_como, api, mensalidade):
    pagar(api, mensalidade["id"])
    lista = api_como(Perfil.CONSULTA).get("/api/mensalidades").json()
    assert lista[0]["pagamento"]["valor_pago"] == "150.00"


def test_token_invalido_nao_registra(sem_login, mensalidade):
    resposta = sem_login.post(
        f"/api/mensalidades/{mensalidade['id']}/pagamento",
        json={"data_pagamento": "2026-11-05", "valor_pago": "150.00", "forma_pagamento": "pix"},
        headers={"Authorization": "Bearer invalido"},
    )
    assert resposta.status_code == 401


@pytest.mark.parametrize("metodo", ["get", "put", "patch", "delete"])
def test_pagamento_nao_pode_ser_lido_editado_nem_apagado_por_aqui(api, mensalidade, metodo):
    """Nenhum lançamento é apagado nem editado (RN12): só existe o POST."""
    resposta = getattr(api, metodo)(f"/api/mensalidades/{mensalidade['id']}/pagamento")
    assert resposta.status_code == 405


# ---------- Desempenho: a lista não faz uma consulta por linha ----------


def contar_consultas(cliente, db) -> int:
    # Esquece o que a sessão de teste já tem na memória: sem isso, um carregamento preguiçoso
    # (uma consulta por linha) passaria despercebido, porque os usuários já estariam carregados
    db.expire_all()
    total = 0

    def conta(*_):
        nonlocal total
        total += 1

    event.listen(engine, "before_cursor_execute", conta)
    try:
        assert cliente.get("/api/mensalidades", params={"mes": "2026-11"}).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", conta)
    return total


def test_listar_pagamentos_nao_faz_uma_consulta_por_mensalidade(api, api_como, db, matricula):
    for _ in range(2):
        matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    for m in api.get("/api/mensalidades").json():
        # Cada pagamento por um operador diferente: é o que faria uma consulta por linha
        pagar(api_como(Perfil.OPERADOR), m["id"])
    com_2 = contar_consultas(api, db)

    for _ in range(6):
        matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    for m in api.get("/api/mensalidades").json():
        if m["status"] == "pendente":
            pagar(api_como(Perfil.OPERADOR), m["id"])
    com_8 = contar_consultas(api, db)

    assert len(api.get("/api/mensalidades").json()) == 8
    assert com_8 == com_2


# ---------- Regras garantidas pelo banco ----------


def nova_linha(db, mensalidade_id: int, **campos) -> Pagamento:
    usuario_id = db.scalars(select(Mensalidade.criado_por_id)).first()
    pagamento = Pagamento(
        mensalidade_id=mensalidade_id,
        data_pagamento=date(2026, 11, 5),
        valor_pago=Decimal("150.00"),
        forma_pagamento=FormaDePagamento.PIX,
        criado_por_id=usuario_id,
        **campos,
    )
    db.add(pagamento)
    return pagamento


def test_banco_recusa_dois_pagamentos_ativos_da_mesma_mensalidade(db, mensalidade):
    nova_linha(db, mensalidade["id"])
    db.flush()
    nova_linha(db, mensalidade["id"])
    with pytest.raises(IntegrityError, match="uq_pagamentos_mensalidade_ativo"):
        db.flush()


def test_banco_aceita_novo_pagamento_depois_de_um_cancelado(db, mensalidade):
    """Prepara o RF17: o pagamento cancelado deixa de contar e a mensalidade recebe outro."""
    nova_linha(db, mensalidade["id"], cancelado_em=func.now())
    nova_linha(db, mensalidade["id"])
    db.flush()
    assert db.scalar(select(func.count()).select_from(Pagamento)) == 2


@pytest.mark.parametrize("valor", [Decimal("0.00"), Decimal("-1.00")])
def test_banco_recusa_valor_zero_ou_negativo(db, mensalidade, valor):
    linha = nova_linha(db, mensalidade["id"])
    linha.valor_pago = valor
    with pytest.raises(IntegrityError, match="ck_pagamentos_valor_positivo"):
        db.flush()


def test_banco_recusa_forma_fora_da_lista(db, mensalidade):
    # SQL direto: o modelo nem deixaria montar uma forma que não existe
    with pytest.raises(IntegrityError, match="ck_pagamentos_forma_pagamento"):
        db.execute(
            text(
                "INSERT INTO pagamentos (mensalidade_id, data_pagamento, valor_pago,"
                " forma_pagamento, criado_por_id) VALUES (:m, '2026-11-05', 150, 'cartao', :u)"
            ),
            {"m": mensalidade["id"], "u": db.scalars(select(Mensalidade.criado_por_id)).first()},
        )


def test_banco_exige_mensalidade_existente(db, mensalidade):
    nova_linha(db, 999999)
    with pytest.raises(IntegrityError, match="fk_pagamentos_mensalidade_id_mensalidades"):
        db.flush()
