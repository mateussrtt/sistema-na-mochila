from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import alunos, health, matriculas, responsaveis

settings = get_settings()

app = FastAPI(
    title="Na Mochila — API de gestão financeira",
    version="0.1.0",
    description="API do sistema de gestão do Na Mochila: alunos, mensalidades, despesas, "
    "receitas e fluxo de caixa.",
)

# Permite que o frontend (outro endereço) chame a API pelo navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Todas as rotas ficam sob /api
app.include_router(health.router, prefix="/api")
app.include_router(alunos.router, prefix="/api")
app.include_router(responsaveis.router, prefix="/api")
app.include_router(matriculas.router, prefix="/api")
