"""Cria o primeiro administrador do sistema.

Uso: python -m app.criar_admin

Lê ADMIN_EMAIL, ADMIN_SENHA e ADMIN_NOME do ambiente (ou do .env). Se já existir um
administrador ativo, não faz nada. Roda no Render antes de a API subir, já que o plano
gratuito não tem terminal para criar o usuário na mão.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.seguranca import gerar_hash
from app.db.session import SessionLocal
from app.models import Perfil, Usuario
from app.schemas.usuario import SENHA_MINIMA


def criar_admin(db: Session, nome: str, email: str, senha: str) -> str:
    """Cria o administrador, se ainda não houver um. Devolve o que aconteceu."""
    ja_existe = db.scalar(
        select(Usuario.id).where(Usuario.perfil == Perfil.ADMINISTRADOR, Usuario.ativo.is_(True))
    )
    if ja_existe is not None:
        return "Já existe um administrador ativo. Nada foi feito."
    if len(senha) < SENHA_MINIMA:
        raise ValueError(f"ADMIN_SENHA precisa ter pelo menos {SENHA_MINIMA} caracteres")

    db.add(
        Usuario(
            nome=nome,
            email=email.strip().lower(),
            senha_hash=gerar_hash(senha),
            perfil=Perfil.ADMINISTRADOR,
        )
    )
    db.commit()
    return f"Administrador {email} criado."


def main() -> None:
    config = get_settings()
    if not config.admin_email or not config.admin_senha:
        print("ADMIN_EMAIL e ADMIN_SENHA não definidos. Nenhum administrador criado.")
        return
    with SessionLocal() as db:
        print(criar_admin(db, config.admin_nome, config.admin_email, config.admin_senha))


if __name__ == "__main__":
    main()
