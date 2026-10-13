from fastapi import FastAPI

from app.routers import health

app = FastAPI(
    title="Na Mochila — API de gestão financeira",
    version="0.1.0",
    description="API do sistema de gestão do Na Mochila: alunos, mensalidades, despesas, "
    "receitas e fluxo de caixa.",
)

# Todas as rotas ficam sob /api
app.include_router(health.router, prefix="/api")
