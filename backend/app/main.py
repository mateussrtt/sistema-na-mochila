from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@app.exception_handler(RequestValidationError)
async def erro_de_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
    """Responde 422 só com o campo e a mensagem de cada erro.

    O padrão do FastAPI devolve também o valor enviado. Quando esse valor tem Unicode
    inválido, a própria resposta de erro quebrava e virava erro 500. Assim também não
    repetimos dados pessoais na resposta.
    """
    detalhes = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in erro.errors()]
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": detalhes}))


# Todas as rotas ficam sob /api
app.include_router(health.router, prefix="/api")
app.include_router(alunos.router, prefix="/api")
app.include_router(responsaveis.router, prefix="/api")
app.include_router(matriculas.router, prefix="/api")
