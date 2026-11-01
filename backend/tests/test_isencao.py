from datetime import date

import pytest
from sqlalchemy import event, func, select, text, update
from sqlalchemy.exc import DataError, IntegrityError

from app.core import tempo
from app.db.session import engine
from app.models import Mensalidade, Perfil, StatusMensalidade, Usuario

HOJE = date(2026, 11, 5)
ACOES = [("isentar", "isenta"), ("cancelar", "cancelada")]


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


def alterar(cliente, alvo, acao, **corpo):
    dados = {"motivo": "Recesso de fim de ano"} | corpo
    return cliente.patch(f"/api/mensalidades/{alvo}/{acao}", json=dados)


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


def do_banco(db) -> Mensalidade:
    db.expire_all()
    return db.scalars(select(Mensalidade)).one()


# ---------- Isentar e cancelar ----------


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_altera_a_situacao_e_guarda_motivo_autor_e_hora(api, db, mensalidade, acao, status):
    eu = api.get("/api/auth/eu").json()

    resposta = alterar(api, mensalidade["id"], acao, motivo="Recesso de julho")

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["id"] == mensalidade["id"]
    assert corpo["status"] == status
    assert corpo["situacao"] == status
    assert corpo["motivo"] == "Recesso de julho"
    assert corpo["alterado_por"] == eu["nome"]
    assert corpo["alterado_em"]
    assert corpo["pagamento"] is None
    no_banco = do_banco(db)
    assert no_banco.status == StatusMensalidade(status)
    assert no_banco.motivo_alteracao == "Recesso de julho"
    assert no_banco.alterado_por_id == eu["id"]
    assert no_banco.alterado_em is not None


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_nada_e_apagado_e_o_valor_e_o_vencimento_continuam(api, db, mensalidade, acao, status):
    alterar(api, mensalidade["id"], acao)

    lista = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    assert len(lista) == 1
    assert lista[0]["valor"] == "150.00"
    assert lista[0]["data_vencimento"] == "2026-11-10"
    assert lista[0]["competencia"] == "2026-11-01"
    assert db.scalar(select(func.count()).select_from(Mensalidade)) == 1


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_a_lista_mostra_motivo_quem_alterou_e_quando(api, mensalidade, acao, status):
    alterar(api, mensalidade["id"], acao, motivo="Gerada por engano")

    (item,) = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    assert item["situacao"] == status
    assert item["motivo"] == "Gerada por engano"
    assert item["alterado_por"]
    assert item["alterado_em"]
    assert [m["id"] for m in api.get("/api/mensalidades", params={"situacao": status}).json()] == [
        mensalidade["id"]
    ]


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_resposta_da_rota_e_igual_ao_item_da_lista(api, mensalidade, acao, status):
    resposta = alterar(api, mensalidade["id"], acao).json()
    (item,) = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    assert resposta == item


def test_quem_alterou_e_o_administrador_logado_e_nao_quem_gerou(api, api_como, mensalidade):
    outro = api_como(Perfil.ADMINISTRADOR)
    nome_do_outro = outro.get("/api/auth/eu").json()["nome"]

    alterar(outro, mensalidade["id"], "isentar")

    (item,) = api.get("/api/mensalidades").json()
    assert item["alterado_por"] == nome_do_outro
    assert item["alterado_por"] != api.get("/api/auth/eu").json()["nome"]


def test_a_hora_da_alteracao_e_a_do_servidor(api, mensalidade):
    corpo = alterar(api, mensalidade["id"], "cancelar").json()
    assert corpo["alterado_em"].startswith(str(date.today().year))
    assert "T" in corpo["alterado_em"]


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_isenta_e_cancelada_nunca_ficam_atrasadas(api, monkeypatch, mensalidade, acao, status):
    alterar(api, mensalidade["id"], acao)
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 3, 1))

    (item,) = api.get("/api/mensalidades").json()
    assert item["situacao"] == status
    assert item["dias_em_atraso"] == 0
    assert api.get("/api/mensalidades", params={"situacao": "atrasada"}).json() == []


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_sai_das_pendencias(api, monkeypatch, mensalidade, acao, status):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 20))
    assert api.get("/api/pendencias").json()["resumo"]["mensalidades"] == 1

    alterar(api, mensalidade["id"], acao)

    painel = api.get("/api/pendencias").json()
    assert painel["grupos"] == []
    assert painel["resumo"]["total_em_aberto"] == "0.00"


def test_isentar_uma_de_duas_atrasadas_mantem_a_outra_nas_pendencias(api, monkeypatch, matricula):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, 20))
    matricula("Ana Isenta")
    matricula("Beto Devedor")
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    por_nome = {m["aluno"]["nome"]: m["id"] for m in api.get("/api/mensalidades").json()}

    alterar(api, por_nome["Ana Isenta"], "isentar")

    painel = api.get("/api/pendencias").json()
    nomes = [a["nome"] for g in painel["grupos"] for a in g["alunos"]]
    assert nomes == ["Beto Devedor"]
    assert painel["resumo"]["total_em_aberto"] == "150.00"


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_gerar_de_novo_nao_recria_nem_reabre(api, mensalidade, acao, status):
    alterar(api, mensalidade["id"], acao)

    resultado = api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"}).json()

    assert resultado["geradas"] == 0
    assert resultado["ja_existiam"] == 1
    (item,) = api.get("/api/mensalidades").json()
    assert item["situacao"] == status
    assert item["motivo"] == "Recesso de fim de ano"


@pytest.mark.parametrize(("acao", "status"), ACOES)
def test_nao_recebe_pagamento_depois(api, mensalidade, acao, status):
    alterar(api, mensalidade["id"], acao)
    pagamento = {"data_pagamento": "2026-11-05", "valor_pago": "150.00", "forma_pagamento": "pix"}
    resposta = api.post(f"/api/mensalidades/{mensalidade['id']}/pagamento", json=pagamento)
    assert resposta.status_code == 409


# ---------- Mensalidade paga, isenta ou cancelada não muda (RF14) ----------


def pagar(api, id_):
    pagamento = {"data_pagamento": "2026-11-05", "valor_pago": "150.00", "forma_pagamento": "pix"}
    assert api.post(f"/api/mensalidades/{id_}/pagamento", json=pagamento).status_code == 201


@pytest.mark.parametrize(
    ("acao", "mensagem"),
    [
        ("isentar", "Uma mensalidade paga não pode ser isentada"),
        ("cancelar", "Uma mensalidade paga não pode ser cancelada"),
    ],
)
def test_mensalidade_paga_nao_pode_ser_isentada_nem_cancelada(api, db, mensalidade, acao, mensagem):
    pagar(api, mensalidade["id"])

    resposta = alterar(api, mensalidade["id"], acao)

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == mensagem
    no_banco = do_banco(db)
    assert no_banco.status == StatusMensalidade.PAGA
    assert no_banco.motivo_alteracao is None
    assert no_banco.alterado_por_id is None


@pytest.mark.parametrize(
    ("primeira", "segunda", "mensagem"),
    [
        ("isentar", "isentar", "Esta mensalidade já está isenta"),
        ("isentar", "cancelar", "Uma mensalidade isenta não pode ser cancelada"),
        ("cancelar", "cancelar", "Esta mensalidade já está cancelada"),
        ("cancelar", "isentar", "Uma mensalidade cancelada não pode ser isentada"),
    ],
)
def test_nao_da_para_alterar_duas_vezes_e_o_primeiro_motivo_fica(
    api, api_como, db, mensalidade, primeira, segunda, mensagem
):
    outro_admin = api_como(Perfil.ADMINISTRADOR)
    alterar(api, mensalidade["id"], primeira, motivo="Primeiro motivo")
    antes = do_banco(db)
    quando, quem = antes.alterado_em, antes.alterado_por_id

    resposta = alterar(outro_admin, mensalidade["id"], segunda, motivo="Segundo motivo")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == mensagem
    depois = do_banco(db)
    assert depois.motivo_alteracao == "Primeiro motivo"
    assert (depois.alterado_em, depois.alterado_por_id) == (quando, quem)


# ---------- Motivo obrigatório ----------


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
@pytest.mark.parametrize("motivo", ["", "   ", "\n\t", None])
def test_motivo_vazio_e_recusado(api, db, mensalidade, acao, motivo):
    erros = erros_de(alterar(api, mensalidade["id"], acao, motivo=motivo))
    assert erros["motivo"] == "Informe o motivo"
    no_banco = do_banco(db)
    assert no_banco.status == StatusMensalidade.PENDENTE
    assert no_banco.motivo_alteracao is None


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_sem_o_campo_motivo_e_recusado(api, mensalidade, acao):
    resposta = api.patch(f"/api/mensalidades/{mensalidade['id']}/{acao}", json={})
    assert "motivo" in erros_de(resposta)


@pytest.mark.parametrize("corpo", ["{", "[]", "null", '"texto"', "123", ""])
def test_corpo_malformado_da_422(api, mensalidade, corpo):
    resposta = api.patch(
        f"/api/mensalidades/{mensalidade['id']}/isentar",
        content=corpo,
        headers={"Content-Type": "application/json"},
    )
    assert resposta.status_code == 422


@pytest.mark.parametrize("motivo", [5, True, ["a"], {"a": 1}, 1.5])
def test_motivo_que_nao_e_texto_e_recusado(api, mensalidade, motivo):
    assert "motivo" in erros_de(alterar(api, mensalidade["id"], "isentar", motivo=motivo))


def test_motivo_curto_demais_e_recusado_e_o_minimo_e_aceito(api, mensalidade):
    erros = erros_de(alterar(api, mensalidade["id"], "isentar", motivo="ab"))
    assert erros["motivo"] == "Explique o motivo com pelo menos 3 letras"
    assert alterar(api, mensalidade["id"], "isentar", motivo="abc").status_code == 200


def test_limite_de_255_caracteres_no_motivo(api, matricula):
    matricula("Aluno A")
    matricula("Aluno B")
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    a, b = (m["id"] for m in api.get("/api/mensalidades").json())

    erros = erros_de(alterar(api, a, "isentar", motivo="a" * 256))
    assert erros["motivo"] == "Use no máximo 255 caracteres no motivo"
    # Os espaços das pontas não contam
    resposta = alterar(api, b, "isentar", motivo="  " + "a" * 255 + "  ")
    assert resposta.status_code == 200
    assert resposta.json()["motivo"] == "a" * 255


def test_motivo_e_aparado_e_espacos_repetidos_viram_um(api, mensalidade):
    resposta = alterar(api, mensalidade["id"], "isentar", motivo="  Recesso   de\n julho  ")
    assert resposta.json()["motivo"] == "Recesso de julho"


def test_motivo_com_acentos_e_emoji(api, mensalidade):
    texto = "Família sem renda — João 🙂"
    assert alterar(api, mensalidade["id"], "cancelar", motivo=texto).json()["motivo"] == texto


def test_motivo_com_caractere_nulo_e_recusado(api, db, mensalidade):
    erros = erros_de(alterar(api, mensalidade["id"], "isentar", motivo="texto" + chr(0) + "nulo"))
    assert erros["motivo"] == "O texto tem um caractere inválido"
    assert do_banco(db).status == StatusMensalidade.PENDENTE


def test_o_erro_nao_repete_o_que_foi_enviado(api, mensalidade):
    resposta = alterar(api, mensalidade["id"], "isentar", motivo="segredo" + chr(0))
    assert resposta.status_code == 422
    assert "segredo" not in resposta.text


def test_campos_extras_sao_ignorados(api, db, mensalidade):
    resposta = alterar(
        api,
        mensalidade["id"],
        "isentar",
        status="paga",
        alterado_por_id=999,
        alterado_em="2000-01-01T00:00:00",
        valor="1.00",
        id=77,
    )
    assert resposta.status_code == 200
    no_banco = do_banco(db)
    assert no_banco.status == StatusMensalidade.ISENTA
    assert no_banco.alterado_por_id != 999
    assert no_banco.alterado_em.year >= 2026
    assert str(no_banco.valor) == "150.00"


# ---------- Mensalidade inexistente e ids fora do normal ----------


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_mensalidade_inexistente_da_404(api, acao):
    resposta = alterar(api, 999999, acao)
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Mensalidade não encontrada"


@pytest.mark.parametrize("id_", [0, -1, 2_147_483_648, 99999999999999999999, "abc", "1.5"])
@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_id_fora_do_normal_da_422_e_nao_500(api, acao, id_):
    assert alterar(api, id_, acao).status_code == 422


def test_o_maior_id_possivel_da_404(api):
    assert alterar(api, 2_147_483_647, "isentar").status_code == 404


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
@pytest.mark.parametrize("metodo", ["get", "post", "put", "delete"])
def test_so_aceita_patch(api, mensalidade, acao, metodo):
    """Nada é apagado nem editado por outro caminho (RN12)."""
    resposta = getattr(api, metodo)(f"/api/mensalidades/{mensalidade['id']}/{acao}")
    assert resposta.status_code == 405


# ---------- Só o administrador (RN13) ----------


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_sem_login_nao_altera(sem_login, acao):
    assert (
        sem_login.patch(f"/api/mensalidades/1/{acao}", json={"motivo": "teste"}).status_code == 401
    )


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_token_invalido_nao_altera(sem_login, acao):
    resposta = sem_login.patch(
        f"/api/mensalidades/1/{acao}",
        json={"motivo": "teste"},
        headers={"Authorization": "Bearer invalido"},
    )
    assert resposta.status_code == 401


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.CONSULTA])
@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_so_o_administrador_isenta_e_cancela(api_como, db, mensalidade, perfil, acao):
    resposta = alterar(api_como(perfil), mensalidade["id"], acao)
    assert resposta.status_code == 403
    no_banco = do_banco(db)
    assert no_banco.status == StatusMensalidade.PENDENTE
    assert no_banco.motivo_alteracao is None


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_o_perfil_e_conferido_antes_de_tudo(api_como, acao):
    """O operador não descobre se a mensalidade existe nem se o motivo está certo."""
    operador = api_como(Perfil.OPERADOR)
    assert alterar(operador, 999999, acao).status_code == 403
    assert operador.patch(f"/api/mensalidades/999999/{acao}", json={}).status_code == 403


@pytest.mark.parametrize("acao", ["isentar", "cancelar"])
def test_administrador_desativado_nao_altera(api, api_como, db, mensalidade, acao):
    admin = api_como(Perfil.ADMINISTRADOR)
    eu = admin.get("/api/auth/eu").json()
    db.execute(update(Usuario).where(Usuario.id == eu["id"]).values(ativo=False))
    db.flush()
    assert alterar(admin, mensalidade["id"], acao).status_code == 401


def test_todos_os_perfis_veem_o_motivo_na_lista(api, api_como, mensalidade):
    alterar(api, mensalidade["id"], "isentar", motivo="Recesso de julho")
    for perfil in Perfil:
        (item,) = api_como(perfil).get("/api/mensalidades").json()
        assert item["motivo"] == "Recesso de julho"


# ---------- Privacidade e desempenho ----------


def test_resposta_so_traz_o_nome_de_quem_alterou(api, mensalidade):
    resposta = alterar(api, mensalidade["id"], "isentar")
    texto = resposta.text.lower()
    for proibido in ("senha", "email", "@", "perfil", "alterado_por_id"):
        assert proibido not in texto
    assert set(resposta.json()) == {
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


def test_a_lista_nao_faz_uma_consulta_por_mensalidade_alterada(api, api_como, db, matricula):
    def isentar_todas():
        # Cada uma por um administrador diferente: é o que faria uma consulta por linha
        for m in api.get("/api/mensalidades", params={"mes": "2026-11"}).json():
            if m["status"] == "pendente":
                alterar(api_como(Perfil.ADMINISTRADOR), m["id"], "isentar")

    for _ in range(2):
        matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    isentar_todas()
    com_2 = contar_consultas(api, db)

    for _ in range(6):
        matricula()
    api.post("/api/mensalidades/gerar", json={"competencia": "2026-11"})
    isentar_todas()
    com_8 = contar_consultas(api, db)

    assert len(api.get("/api/mensalidades", params={"mes": "2026-11"}).json()) == 8
    assert com_8 == com_2


# ---------- Regras garantidas pelo banco (RN12, RF26) ----------


def atualizar_no_banco(db, **campos):
    db.execute(update(Mensalidade).values(**campos))
    db.flush()


def test_banco_recusa_isenta_sem_motivo_autor_ou_hora(db, api, mensalidade):
    eu = api.get("/api/auth/eu").json()
    completo = {"motivo_alteracao": "teste", "alterado_por_id": eu["id"], "alterado_em": func.now()}
    for faltando in completo:
        campos = {**completo, faltando: None}
        with pytest.raises(IntegrityError, match="isenta_ou_cancelada_com_motivo"):
            with db.begin_nested():
                atualizar_no_banco(db, status="isenta", **campos)


def test_banco_recusa_cancelada_sem_motivo(db, mensalidade):
    with pytest.raises(IntegrityError, match="isenta_ou_cancelada_com_motivo"):
        atualizar_no_banco(db, status="cancelada")


@pytest.mark.parametrize("status", ["isenta", "cancelada"])
def test_banco_aceita_com_os_tres_campos(db, api, mensalidade, status):
    eu = api.get("/api/auth/eu").json()
    atualizar_no_banco(
        db,
        status=status,
        motivo_alteracao="teste",
        alterado_por_id=eu["id"],
        alterado_em=func.now(),
    )
    assert do_banco(db).status == StatusMensalidade(status)


@pytest.mark.parametrize("status", ["pendente", "paga"])
def test_banco_nao_exige_motivo_em_pendente_nem_paga(db, mensalidade, status):
    atualizar_no_banco(db, status=status)
    assert do_banco(db).motivo_alteracao is None


def test_banco_recusa_autor_inexistente(db, mensalidade):
    with pytest.raises(IntegrityError, match="fk_mensalidades_alterado_por_id_usuarios"):
        atualizar_no_banco(
            db,
            status="isenta",
            motivo_alteracao="teste",
            alterado_por_id=999999,
            alterado_em=func.now(),
        )


def test_banco_recusa_motivo_maior_que_255(db, api, mensalidade):
    eu = api.get("/api/auth/eu").json()
    with pytest.raises(DataError):
        db.execute(
            text(
                "UPDATE mensalidades SET status = 'isenta', motivo_alteracao = :m,"
                " alterado_por_id = :u, alterado_em = now()"
            ),
            {"m": "a" * 256, "u": eu["id"]},
        )
