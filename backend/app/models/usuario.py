import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Perfil(enum.StrEnum):
    ADMINISTRADOR = "administrador"
    OPERADOR = "operador"
    CONSULTA = "consulta"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    # Guardado sempre em minúsculas, para o login não depender de maiúsculas
    email: Mapped[str] = mapped_column(String(254), unique=True)
    # Só o hash da senha é guardado, nunca a senha em si
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[Perfil] = mapped_column(
        Enum(
            Perfil,
            name="perfil",
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda perfis: [p.value for p in perfis],
        )
    )
    # Usuário desativado não consegue entrar, mas continua no histórico
    ativo: Mapped[bool] = mapped_column(server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
