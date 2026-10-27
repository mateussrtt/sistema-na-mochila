import pytest
from sqlalchemy import select

from app.core.seguranca import senha_confere
from app.criar_admin import criar_admin
from app.models import Perfil, Usuario


def admins(db):
    return list(db.scalars(select(Usuario).where(Usuario.perfil == Perfil.ADMINISTRADOR)))


@pytest.fixture
def sem_admins(db):
    """Desativa os administradores que já existam no banco, só dentro deste teste."""
    for usuario in admins(db):
        usuario.ativo = False
    db.flush()


def test_cria_o_primeiro_administrador(db, sem_admins):
    criar_admin(db, "Coordenação", "  Coord@NaMochila.org ", "senha-forte-123")
    novo = db.scalar(select(Usuario).where(Usuario.email == "coord@namochila.org"))
    assert novo is not None
    assert novo.perfil == Perfil.ADMINISTRADOR
    assert senha_confere("senha-forte-123", novo.senha_hash)


def test_nao_cria_outro_se_ja_existe_administrador(db, sem_admins):
    criar_admin(db, "Primeiro", "primeiro@namochila.org", "senha-forte-123")
    mensagem = criar_admin(db, "Segundo", "segundo@namochila.org", "senha-forte-123")
    assert "Nada foi feito" in mensagem
    assert db.scalar(select(Usuario).where(Usuario.email == "segundo@namochila.org")) is None


def test_recusa_senha_curta(db, sem_admins):
    with pytest.raises(ValueError):
        criar_admin(db, "Coordenação", "coord@namochila.org", "123")
