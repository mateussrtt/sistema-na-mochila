def test_cadastra_responsavel(api):
    resposta = api.post(
        "/api/responsaveis",
        json={"nome": "  Maria   Souza ", "telefone": "(31) 98888-7777", "email": ""},
    )
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["nome"] == "Maria Souza"
    assert dados["email"] is None


def test_responsavel_exige_telefone_ou_email(api):
    resposta = api.post("/api/responsaveis", json={"nome": "Sem Contato"})
    assert resposta.status_code == 422


def test_responsavel_rejeita_telefone_invalido(api):
    resposta = api.post("/api/responsaveis", json={"nome": "João", "telefone": "1234"})
    assert resposta.status_code == 422


def test_responsavel_rejeita_email_invalido(api):
    resposta = api.post("/api/responsaveis", json={"nome": "João", "email": "joao@"})
    assert resposta.status_code == 422


def test_busca_responsavel_por_nome(api):
    api.post("/api/responsaveis", json={"nome": "Carla Mendes", "email": "carla@exemplo.com"})
    api.post("/api/responsaveis", json={"nome": "Paulo Lima", "email": "paulo@exemplo.com"})
    nomes = [r["nome"] for r in api.get("/api/responsaveis", params={"busca": "carla"}).json()]
    assert nomes == ["Carla Mendes"]


def test_edita_responsavel(api):
    criado = api.post("/api/responsaveis", json={"nome": "Ana", "email": "ana@exemplo.com"}).json()
    resposta = api.put(
        f"/api/responsaveis/{criado['id']}",
        json={"nome": "Ana Clara", "email": "ana@exemplo.com", "telefone": "3138521234"},
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Ana Clara"


def test_responsavel_inexistente(api):
    assert api.get("/api/responsaveis/999999").status_code == 404
