from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core import tempo
from app.models import (
    Mensalidade,
    Perfil,
    SituacaoMensalidade,
    StatusMensalidade,
    data_de_vencimento,
    situacao_da_mensalidade,
)
from app.routers import mensalidades as rota_mensalidades
from app.schemas.mensalidade import primeiro_dia_do_mes

HOJE = date(2026, 11, 5)
# Guardada antes de qualquer teste trocar a função, para testar o relógio de verdade
RELOGIO_REAL = tempo.hoje


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Todos os testes rodam "em 5 de novembro de 2026", para não dependerem do dia em que rodam."""
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)


def gerar(cliente, competencia="2026-11"):
    return cliente.post("/api/mensalidades/gerar", json={"competencia": competencia})


def listar(cliente, **parametros):
    resposta = cliente.get("/api/mensalidades", params=parametros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# ---------- Geração ----------


def test_gera_uma_mensalidade_por_matricula_ativa(api, matricula):
    primeira, segunda = matricula(), matricula(valor_mensalidade="200.00")

    resposta = gerar(api)

    assert resposta.status_code == 200
    assert resposta.json() == {
        "competencia": "2026-11-01",
        "geradas": 2,
        "ja_existiam": 0,
        "bolsa_integral": 0,
        "ainda_nao_comecaram": 0,
    }
    mensalidades = {m["matricula_id"]: m for m in listar(api, mes="2026-11")}
    assert set(mensalidades) == {primeira["id"], segunda["id"]}
    assert mensalidades[primeira["id"]]["valor"] == "150.00"
    assert mensalidades[segunda["id"]]["valor"] == "200.00"


def test_vencimento_e_no_dia_10_e_comeca_pendente(api, matricula):
    matricula()
    gerar(api)
    mensalidade = listar(api, mes="2026-11")[0]
    assert mensalidade["competencia"] == "2026-11-01"
    assert mensalidade["data_vencimento"] == "2026-11-10"
    assert mensalidade["status"] == "pendente"


def test_guarda_quem_gerou_e_quando(api_como, db, matricula):
    matricula()
    operador = api_como(Perfil.OPERADOR)
    quem_e = operador.get("/api/auth/eu").json()["id"]
    gerar(operador)
    mensalidade = db.scalars(select(Mensalidade)).one()
    assert mensalidade.criado_por_id == quem_e
    assert mensalidade.criado_em is not None


def test_gerar_de_novo_o_mesmo_mes_nao_duplica(api, matricula):
    matricula()
    gerar(api)
    segunda = gerar(api).json()
    assert segunda["geradas"] == 0
    assert segunda["ja_existiam"] == 1
    assert len(listar(api, mes="2026-11")) == 1


def test_gerar_de_novo_so_acrescenta_o_que_faltava(api, matricula):
    matricula()
    gerar(api)
    matricula()  # matrícula nova, feita depois da primeira geração
    resultado = gerar(api).json()
    assert (resultado["geradas"], resultado["ja_existiam"]) == (1, 1)
    assert len(listar(api, mes="2026-11")) == 2


def test_cada_mes_tem_a_sua_mensalidade(api, matricula):
    matricula()
    gerar(api, "2026-10")
    gerar(api, "2026-11")
    assert len(listar(api)) == 2
    assert len(listar(api, mes="2026-10")) == 1


def test_bolsa_integral_nao_gera_mensalidade(api, matricula):
    matricula(bolsa="integral", valor_mensalidade="")
    matricula()
    resultado = gerar(api).json()
    assert resultado["geradas"] == 1
    assert resultado["bolsa_integral"] == 1
    assert len(listar(api, mes="2026-11")) == 1


def test_bolsa_parcial_paga_o_valor_com_desconto(api, matricula):
    matricula(bolsa="parcial", valor_mensalidade="75,50")
    gerar(api)
    mensalidade = listar(api, mes="2026-11")[0]
    assert mensalidade["valor"] == "75.50"
    assert mensalidade["bolsa"] == "parcial"


def test_matricula_que_comeca_depois_do_mes_fica_de_fora(api, matricula):
    matricula(data_inicio="2026-12-01")
    resultado = gerar(api).json()
    assert (resultado["geradas"], resultado["ainda_nao_comecaram"]) == (0, 1)
    assert listar(api) == []


@pytest.mark.parametrize(
    ("inicio", "entra"),
    [("2026-11-01", True), ("2026-11-30", True), ("2026-12-01", False), ("2026-10-31", True)],
)
def test_limite_do_inicio_da_matricula(api, matricula, inicio, entra):
    matricula(data_inicio=inicio)
    resultado = gerar(api).json()
    assert resultado["geradas"] == int(entra)
    # só conta como "ainda não começou" quem começa depois do último dia do mês
    assert resultado["ainda_nao_comecaram"] == int(not entra)


def test_matricula_encerrada_nao_gera(api, matricula):
    encerrada = matricula()
    api.patch(
        f"/api/matriculas/{encerrada['id']}/encerrar", json={"data_encerramento": "2026-02-01"}
    )
    matricula()
    assert gerar(api).json()["geradas"] == 1


def test_sem_matriculas_nao_gera_nada_e_nao_da_erro(api):
    resultado = gerar(api)
    assert resultado.status_code == 200
    assert resultado.json()["geradas"] == 0


def test_gera_para_muitas_matriculas_de_uma_vez(api, matricula):
    for _ in range(25):
        matricula()
    assert gerar(api).json()["geradas"] == 25
    assert len(listar(api, mes="2026-11")) == 25


def test_duas_geracoes_ao_mesmo_tempo_nao_duplicam(api, db, cria_usuario, matricula, monkeypatch):
    """Simula a corrida: a checagem não enxerga a mensalidade que a outra geração acabou de criar.

    Quem segura a duplicata, nesse caso, é a restrição única do banco.
    """
    pronta = matricula()
    db.add(
        Mensalidade(
            matricula_id=pronta["id"],
            competencia=date(2026, 11, 1),
            valor=Decimal("150"),
            data_vencimento=date(2026, 11, 10),
            criado_por_id=cria_usuario().id,
        )
    )
    db.flush()
    monkeypatch.setattr(rota_mensalidades, "alunos_ja_cobrados", lambda db, competencia: set())

    resposta = gerar(api)

    assert resposta.status_code == 200
    assert (resposta.json()["geradas"], resposta.json()["ja_existiam"]) == (0, 1)
    assert len(listar(api, mes="2026-11")) == 1


def test_mensalidade_que_ja_existe_nao_derruba_a_geracao(api, db, cria_usuario, matricula):
    """Simula duas pessoas gerando o mesmo mês: o banco ignora a que já existe."""
    pronta, nova = matricula(), matricula()
    db.add(
        Mensalidade(
            matricula_id=pronta["id"],
            competencia=date(2026, 11, 1),
            valor=Decimal("150"),
            data_vencimento=date(2026, 11, 10),
            criado_por_id=cria_usuario().id,
        )
    )
    db.flush()
    resultado = gerar(api).json()
    assert (resultado["geradas"], resultado["ja_existiam"]) == (1, 1)
    assert {m["matricula_id"] for m in listar(api, mes="2026-11")} == {pronta["id"], nova["id"]}


# ---------- Matrícula em vigor no mês e vencimento do primeiro mês ----------


def encerrar(api, matricula_id, em):
    resposta = api.patch(f"/api/matriculas/{matricula_id}/encerrar", json={"data_encerramento": em})
    assert resposta.status_code == 200, resposta.text


@pytest.mark.parametrize(
    ("encerrada_em", "mes", "gera"),
    [
        ("2026-10-15", "2026-10", True),  # saiu no meio do mês: o mês da saída é cobrado
        ("2026-10-15", "2026-11", False),  # e o mês seguinte não
        ("2026-10-31", "2026-10", True),  # saiu no último dia do mês
        ("2026-10-01", "2026-10", True),  # saiu no primeiro dia do mês
        ("2026-09-30", "2026-10", False),  # saiu no último dia do mês anterior
        ("2026-09-30", "2026-09", True),
        ("2026-10-15", "2026-09", True),  # um mês passado também pode ser gerado depois
    ],
)
def test_matricula_encerrada_gera_ate_o_mes_da_saida(api, matricula, encerrada_em, mes, gera):
    encerrar(api, matricula()["id"], encerrada_em)
    assert gerar(api, mes).json()["geradas"] == int(gera)


def test_o_resultado_nao_depende_do_dia_em_que_se_gera(api, matricula, monkeypatch):
    """Quem saiu em 15/10 é cobrado em outubro, gere-se antes ou depois da saída."""
    antes, depois = matricula(), matricula()

    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 10, 5))
    assert gerar(api, "2026-10").json()["geradas"] == 2  # as duas ainda estão ativas

    encerrar(api, antes["id"], "2026-10-15")
    encerrar(api, depois["id"], "2026-10-15")
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 10, 20))
    repetida = gerar(api, "2026-10").json()
    assert (repetida["geradas"], repetida["ja_existiam"]) == (0, 2)
    assert len(listar(api, mes="2026-10")) == 2


def test_gerar_depois_da_saida_cobra_o_mes_da_saida(api, matricula, monkeypatch):
    saiu = matricula()
    encerrar(api, saiu["id"], "2026-10-15")
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 10, 20))
    assert gerar(api, "2026-10").json()["geradas"] == 1
    assert [m["matricula_id"] for m in listar(api, mes="2026-10")] == [saiu["id"]]


@pytest.mark.parametrize(
    ("inicio", "vence"),
    [
        ("2026-10-20", "2026-10-20"),  # entrou depois do dia 10: vence no próprio dia
        ("2026-10-11", "2026-10-11"),
        ("2026-10-10", "2026-10-10"),
        ("2026-10-05", "2026-10-10"),  # entrou antes do dia 10: vence no dia 10
        ("2026-10-01", "2026-10-10"),
        ("2026-10-31", "2026-10-31"),
        ("2026-01-15", "2026-10-10"),  # matrícula antiga: vence no dia 10
    ],
)
def test_vencimento_da_primeira_mensalidade(api, matricula, inicio, vence):
    matricula(data_inicio=inicio)
    gerar(api, "2026-10")
    assert listar(api, mes="2026-10")[0]["data_vencimento"] == vence


def test_vencimento_volta_a_ser_dia_10_no_mes_seguinte(api, matricula):
    matricula(data_inicio="2026-10-20")
    gerar(api, "2026-11")
    assert listar(api, mes="2026-11")[0]["data_vencimento"] == "2026-11-10"


def test_quem_entra_depois_do_dia_10_nao_nasce_atrasado(api, matricula, monkeypatch):
    matricula(data_inicio="2026-10-20")
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 10, 20))
    gerar(api, "2026-10")
    assert listar(api, mes="2026-10")[0]["situacao"] == "a_vencer"
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 10, 21))
    mensalidade = listar(api, mes="2026-10")[0]
    assert (mensalidade["situacao"], mensalidade["dias_em_atraso"]) == ("atrasada", 1)


@pytest.mark.parametrize(
    ("competencia", "inicio", "esperado"),
    [
        (date(2026, 10, 1), date(2026, 10, 20), date(2026, 10, 20)),
        (date(2026, 10, 1), date(2026, 10, 10), date(2026, 10, 10)),
        (date(2026, 10, 1), date(2026, 10, 9), date(2026, 10, 10)),
        (date(2026, 10, 1), date(2025, 3, 1), date(2026, 10, 10)),
        (date(2028, 2, 1), date(2028, 2, 29), date(2028, 2, 29)),  # ano bissexto
    ],
)
def test_regra_do_vencimento(competencia, inicio, esperado):
    assert data_de_vencimento(competencia, inicio) == esperado


def test_aluno_que_sai_e_volta_no_mesmo_mes_nao_e_cobrado_em_dobro(api, novo_aluno, monkeypatch):
    aluno = novo_aluno()["id"]

    def matricular(inicio, valor):
        resposta = api.post(
            "/api/matriculas",
            json={"aluno_id": aluno, "data_inicio": inicio, "valor_mensalidade": valor},
        )
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    primeira = matricular("2026-01-15", "100")
    encerrar(api, primeira["id"], "2026-10-10")
    segunda = matricular("2026-10-20", "120")

    resultado = gerar(api, "2026-10").json()
    assert resultado["geradas"] == 1
    mensalidades = listar(api, mes="2026-10")
    assert len(mensalidades) == 1
    assert mensalidades[0]["matricula_id"] == segunda["id"]  # vale a mais recente
    assert (mensalidades[0]["valor"], mensalidades[0]["data_vencimento"]) == (
        "120.00",
        "2026-10-20",
    )
    assert gerar(api, "2026-10").json()["geradas"] == 0


def test_matricula_nova_nao_gera_segunda_cobranca_se_o_aluno_ja_foi_cobrado(api, novo_aluno):
    aluno = novo_aluno()["id"]
    dados = {"aluno_id": aluno, "data_inicio": "2026-01-15", "valor_mensalidade": "100"}
    primeira = api.post("/api/matriculas", json=dados).json()
    assert gerar(api, "2026-10").json()["geradas"] == 1

    encerrar(api, primeira["id"], "2026-10-12")
    api.post("/api/matriculas", json=dados | {"data_inicio": "2026-10-20"})
    segunda_geracao = gerar(api, "2026-10").json()

    assert (segunda_geracao["geradas"], segunda_geracao["ja_existiam"]) == (0, 1)
    assert [m["matricula_id"] for m in listar(api, mes="2026-10")] == [primeira["id"]]


def test_se_a_matricula_mais_recente_e_bolsa_integral_o_aluno_nao_e_cobrado(api, novo_aluno):
    aluno = novo_aluno()["id"]
    dados = {"aluno_id": aluno, "data_inicio": "2026-01-15", "valor_mensalidade": "100"}
    primeira = api.post("/api/matriculas", json=dados).json()
    encerrar(api, primeira["id"], "2026-10-10")
    api.post(
        "/api/matriculas",
        json={"aluno_id": aluno, "data_inicio": "2026-10-20", "bolsa": "integral"},
    )

    resultado = gerar(api, "2026-10").json()
    assert (resultado["geradas"], resultado["bolsa_integral"]) == (0, 1)


# ---------- Qual mês pode ser gerado ----------


@pytest.mark.parametrize(
    ("hoje", "competencia"),
    [
        (date(2026, 11, 5), "2026-12"),  # o mês seguinte
        (date(2026, 11, 5), "2026-01"),  # meses passados, para recuperar o que faltou
        (date(2026, 12, 15), "2027-01"),  # virada de ano
        (date(2028, 2, 20), "2028-02-29"),  # ano bissexto, e a data vira o dia 1
        (date(2026, 11, 5), "2000-01"),  # o mais antigo aceito
    ],
)
def test_meses_aceitos(api, matricula, monkeypatch, hoje, competencia):
    monkeypatch.setattr(tempo, "hoje", lambda: hoje)
    matricula()
    resposta = gerar(api, competencia)
    assert resposta.status_code == 200
    assert resposta.json()["competencia"].endswith("-01")


@pytest.mark.parametrize(
    ("hoje", "competencia"),
    [
        (date(2026, 11, 5), "2027-01"),  # dois meses adiante
        (date(2026, 11, 5), "2062-11"),  # erro de digitação no ano
        (date(2026, 12, 15), "2027-02"),
        (date(2026, 11, 5), "1999-12"),
    ],
)
def test_meses_recusados(api, monkeypatch, hoje, competencia):
    monkeypatch.setattr(tempo, "hoje", lambda: hoje)
    assert gerar(api, competencia).status_code == 422


def test_primeiro_dia_do_mes_aceita_uma_data_pronta():
    assert primeiro_dia_do_mes(date(2026, 11, 23)) == date(2026, 11, 1)


def test_competencia_com_dia_vira_o_primeiro_dia_do_mes(api, matricula):
    matricula()
    assert gerar(api, "2026-11-23").json()["competencia"] == "2026-11-01"


@pytest.mark.parametrize(
    "competencia",
    ["", "  ", None, "2026-13", "2026-00", "2026-02-30", "novembro", 202611, "2026-1", "2026/11"]
    + ["２０２６-１１", "2026-11-1", [], {}, True, "2026-11-01T00:00:00", "9999-12", "0001-01"],
)
def test_competencia_invalida_vira_422(api, competencia):
    assert gerar(api, competencia).status_code == 422


def test_corpo_sem_competencia_ou_malformado_vira_422(api):
    cabecalho = {"Content-Type": "application/json"}
    assert api.post("/api/mensalidades/gerar", json={}).status_code == 422
    assert api.post("/api/mensalidades/gerar").status_code == 422
    assert api.post("/api/mensalidades/gerar", content=b"{", headers=cabecalho).status_code == 422
    assert api.post("/api/mensalidades/gerar", content=b"[]", headers=cabecalho).status_code == 422


def test_campos_de_controle_enviados_pelo_cliente_sao_ignorados(api, db, matricula):
    matricula()
    extras = {"status": "paga", "criado_por_id": 999999, "valor": "1.00", "id": 1}
    resposta = api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"} | extras)
    assert resposta.status_code == 200
    mensalidade = db.scalars(select(Mensalidade)).one()
    assert mensalidade.status == StatusMensalidade.PENDENTE
    assert mensalidade.valor == Decimal("150.00")
    assert mensalidade.criado_por_id != 999999


# ---------- Permissões ----------


def test_sem_login_nao_gera_nem_lista(sem_login):
    assert gerar(sem_login).status_code == 401
    assert sem_login.get("/api/mensalidades").status_code == 401


def test_consulta_so_visualiza(api_como, api, matricula):
    matricula()
    gerar(api)
    consulta = api_como(Perfil.CONSULTA)
    assert gerar(consulta, "2026-12").status_code == 403
    assert len(listar(consulta, mes="2026-11")) == 1
    assert listar(api, mes="2026-12") == []  # a tentativa da consulta não gerou nada


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.ADMINISTRADOR])
def test_operador_e_administrador_geram(api_como, matricula, perfil):
    matricula()
    assert gerar(api_como(perfil)).json()["geradas"] == 1


# ---------- Situação: a vencer, atrasada, paga, isenta, cancelada ----------


@pytest.mark.parametrize(
    ("hoje", "situacao", "atraso"),
    [
        (date(2026, 11, 1), "a_vencer", 0),
        (date(2026, 11, 10), "a_vencer", 0),  # o dia 10 ainda é "a vencer" (RN07)
        (date(2026, 11, 11), "atrasada", 1),  # a partir do dia 11, atrasada
        (date(2026, 11, 30), "atrasada", 20),
    ],
)
def test_situacao_pela_data_de_hoje(api, matricula, monkeypatch, hoje, situacao, atraso):
    monkeypatch.setattr(tempo, "hoje", lambda: hoje)
    matricula()
    gerar(api)
    mensalidade = listar(api, mes="2026-11")[0]
    assert mensalidade["situacao"] == situacao
    assert mensalidade["dias_em_atraso"] == atraso
    assert mensalidade["status"] == "pendente"  # a situação é calculada, não gravada


@pytest.mark.parametrize(
    ("status", "esperada"),
    [
        (StatusMensalidade.PAGA, "paga"),
        (StatusMensalidade.ISENTA, "isenta"),
        (StatusMensalidade.CANCELADA, "cancelada"),
    ],
)
def test_paga_isenta_e_cancelada_nunca_aparecem_como_atrasadas(
    api, db, matricula, monkeypatch, status, esperada
):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 30))  # bem depois do vencimento
    matricula()
    gerar(api)
    id_ = listar(api, mes="2026-11")[0]["id"]
    if status == StatusMensalidade.PAGA:
        db.scalars(select(Mensalidade)).one().status = status
        db.flush()
    else:
        acao = "isentar" if status == StatusMensalidade.ISENTA else "cancelar"
        alteracao = api.patch(f"/api/mensalidades/{id_}/{acao}", json={"motivo": "Motivo de teste"})
        assert alteracao.status_code == 200

    mensalidade = listar(api, mes="2026-11")[0]
    assert mensalidade["situacao"] == esperada
    assert mensalidade["dias_em_atraso"] == 0
    assert listar(api, mes="2026-11", situacao="atrasada") == []
    assert len(listar(api, mes="2026-11", situacao=esperada)) == 1


@pytest.mark.parametrize(
    ("status", "vencimento", "hoje", "esperada"),
    [
        (StatusMensalidade.PENDENTE, date(2026, 11, 10), date(2026, 11, 10), "a_vencer"),
        (StatusMensalidade.PENDENTE, date(2026, 11, 10), date(2026, 11, 11), "atrasada"),
        (StatusMensalidade.PENDENTE, date(2026, 11, 10), date(2026, 11, 9), "a_vencer"),
        (StatusMensalidade.PENDENTE, date(2026, 12, 31), date(2027, 1, 1), "atrasada"),
        (StatusMensalidade.PAGA, date(2020, 1, 10), date(2026, 11, 5), "paga"),
        (StatusMensalidade.ISENTA, date(2020, 1, 10), date(2026, 11, 5), "isenta"),
        (StatusMensalidade.CANCELADA, date(2020, 1, 10), date(2026, 11, 5), "cancelada"),
    ],
)
def test_regra_da_situacao(status, vencimento, hoje, esperada):
    assert situacao_da_mensalidade(status, vencimento, hoje) == SituacaoMensalidade(esperada)


def test_o_dia_10_as_22h_em_brasilia_ainda_nao_esta_atrasada(monkeypatch):
    """O servidor roda em UTC: 22h30 do dia 10 em Brasília já é dia 11 na hora de lá."""

    class RelogioFalso(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 11, 1, 30, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(tempo, "datetime", RelogioFalso)
    assert RELOGIO_REAL() == date(2026, 11, 10)
    assert (
        situacao_da_mensalidade(StatusMensalidade.PENDENTE, date(2026, 11, 10), RELOGIO_REAL())
        == SituacaoMensalidade.A_VENCER
    )


# ---------- Listagem e filtros ----------


def test_lista_vazia(api):
    assert listar(api) == []


def test_filtra_por_mes(api, matricula):
    matricula()
    gerar(api, "2026-10")
    gerar(api, "2026-11")
    assert [m["competencia"] for m in listar(api, mes="2026-10")] == ["2026-10-01"]
    assert [m["competencia"] for m in listar(api, mes="2026-11-17")] == ["2026-11-01"]
    assert listar(api, mes="2026-09") == []
    assert len(listar(api, mes="")) == 2  # vazio = todos os meses


@pytest.mark.parametrize("mes", ["2026-13", "abc", "2026-1", "０", "2026-11-31", "x" * 11])
def test_mes_invalido_no_filtro_vira_422(api, mes):
    resposta = api.get("/api/mensalidades", params={"mes": mes})
    assert resposta.status_code == 422
    # Mesmo formato dos outros erros de validação: lista com o campo e a mensagem
    assert resposta.json()["detail"][0]["loc"] == ["query", "mes"]


def test_filtra_por_situacao(api, db, matricula, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 10))
    a, b, c = matricula(), matricula(), matricula()
    gerar(api)
    mensalidades = {m.matricula_id: m for m in db.scalars(select(Mensalidade))}
    mensalidades[b["id"]].status = StatusMensalidade.PAGA
    mensalidades[c["id"]].data_vencimento = date(2026, 11, 3)  # venceu antes de "hoje"
    db.flush()

    def ids(situacao):
        return {m["matricula_id"] for m in listar(api, situacao=situacao)}

    assert ids("a_vencer") == {a["id"]}
    assert ids("atrasada") == {c["id"]}
    assert ids("paga") == {b["id"]}
    assert ids("isenta") == ids("cancelada") == set()
    assert ids("todas") == {a["id"], b["id"], c["id"]}


def test_situacao_invalida_no_filtro_vira_422(api):
    assert api.get("/api/mensalidades", params={"situacao": "xyz"}).status_code == 422


def test_busca_pelo_nome_do_aluno(api, matricula):
    matricula("Beatriz Lemos")
    matricula("Carlos Lemos")
    matricula("Diana Rocha")
    gerar(api)

    def nomes(**filtros):
        return [m["aluno"]["nome"] for m in listar(api, **filtros)]

    assert nomes(busca="lemos") == ["Beatriz Lemos", "Carlos Lemos"]
    assert nomes(busca="  DIANA ") == ["Diana Rocha"]
    assert nomes(busca="zzz") == []


@pytest.mark.parametrize("busca", ["%", "_", "\\", "' OR '1'='1", "'; DROP TABLE mensalidades; --"])
def test_busca_trata_o_texto_como_texto(api, db, matricula, busca):
    matricula("Elisa Nunes")
    gerar(api)
    assert listar(api, busca=busca) == []
    assert db.scalar(select(func.count()).select_from(Mensalidade)) == 1


def test_busca_com_caractere_nulo_e_texto_enorme_nao_dao_erro_500(api, matricula):
    matricula("Fabio Alves")
    gerar(api)
    assert len(listar(api, busca="Fabio\x00 Alves")) == 1
    assert listar(api, busca="a" * 10_000) == []


def test_filtra_por_matricula(api, matricula):
    a, b = matricula(), matricula()
    gerar(api)
    assert [m["matricula_id"] for m in listar(api, matricula_id=a["id"])] == [a["id"]]
    assert listar(api, matricula_id=b["id"] + 1000) == []


@pytest.mark.parametrize("matricula_id", [0, -1, 99999999999999, "abc"])
def test_matricula_invalida_no_filtro_vira_422(api, matricula_id):
    assert api.get("/api/mensalidades", params={"matricula_id": matricula_id}).status_code == 422


def test_lista_por_aluno_e_depois_do_mes_mais_recente(api, matricula):
    matricula("Zilda Mota")
    matricula("Adriano Costa")
    gerar(api, "2026-10")
    gerar(api, "2026-11")
    ordem = [(m["aluno"]["nome"], m["competencia"]) for m in listar(api)]
    assert ordem == [
        ("Adriano Costa", "2026-11-01"),
        ("Adriano Costa", "2026-10-01"),
        ("Zilda Mota", "2026-11-01"),
        ("Zilda Mota", "2026-10-01"),
    ]


def test_resposta_traz_so_o_necessario(api, matricula):
    matricula()
    gerar(api)
    mensalidade = listar(api)[0]
    assert set(mensalidade) == {
        "id",
        "matricula_id",
        "aluno",
        "bolsa",
        "competencia",
        "valor",
        "data_vencimento",
        "status",
        "situacao",
        "dias_em_atraso",
        "pagamento",
        "motivo",
        "alterado_por",
        "alterado_em",
    }
    assert mensalidade["pagamento"] is None  # só a mensalidade paga tem pagamento
    # E só a isenta ou cancelada tem motivo, quem alterou e quando
    assert (mensalidade["motivo"], mensalidade["alterado_por"], mensalidade["alterado_em"]) == (
        None,
        None,
        None,
    )
    assert set(mensalidade["aluno"]) == {"id", "nome", "ativo"}
    assert "31977776666" not in api.get("/api/mensalidades").text  # telefone do responsável


def test_mensalidade_nao_pode_ser_apagada_nem_editada_pela_api(api, matricula):
    matricula()
    gerar(api)
    id_ = listar(api)[0]["id"]
    assert api.delete("/api/mensalidades").status_code == 405
    assert api.put("/api/mensalidades", json={}).status_code == 405
    assert api.get("/api/mensalidades/gerar").status_code == 405
    assert api.delete(f"/api/mensalidades/{id_}").status_code in (404, 405)
    assert len(listar(api)) == 1


# ---------- Regras garantidas pelo banco ----------


def nova_mensalidade(matricula_id: int, criado_por_id: int, **campos) -> Mensalidade:
    dados = {
        "matricula_id": matricula_id,
        "competencia": date(2026, 11, 1),
        "valor": Decimal("100.00"),
        "data_vencimento": date(2026, 11, 10),
        "criado_por_id": criado_por_id,
    } | campos
    return Mensalidade(**dados)


def test_banco_nao_aceita_duas_mensalidades_no_mesmo_mes(db, cria_usuario, matricula):
    id_ = matricula()["id"]
    autor = cria_usuario().id
    db.add(nova_mensalidade(id_, autor))
    db.flush()
    db.add(nova_mensalidade(id_, autor))
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "campos",
    [
        {"valor": Decimal("0")},
        {"valor": Decimal("-1.00")},
        {"competencia": date(2026, 11, 2)},
        {"data_vencimento": date(2026, 10, 31)},
    ],
    ids=["valor zero", "valor negativo", "competência fora do dia 1", "vence antes da competência"],
)
def test_banco_recusa_dados_invalidos(db, cria_usuario, matricula, campos):
    db.add(nova_mensalidade(matricula()["id"], cria_usuario().id, **campos))
    with pytest.raises(IntegrityError):
        db.flush()


def test_banco_recusa_status_desconhecido(db, cria_usuario, matricula):
    db.add(nova_mensalidade(matricula()["id"], cria_usuario().id))
    db.flush()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE mensalidades SET status = 'inventado'"))
