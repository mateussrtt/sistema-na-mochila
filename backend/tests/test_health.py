from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responde_ok():
    resposta = client.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_health_conecta_no_banco():
    assert client.get("/api/health").json()["banco"] == "ok"


def test_documentacao_da_api_disponivel():
    assert client.get("/docs").status_code == 200
