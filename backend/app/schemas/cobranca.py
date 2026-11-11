from datetime import date, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ValidationInfo, field_validator

from app.core import tempo
from app.models import FormaDePagamentoCobranca, SituacaoCobranca, StatusCobranca
from app.schemas.cancelamento import CancelamentoLeitura
from app.schemas.comum import texto_valido
from app.schemas.matricula import AlunoResumo, exige_data
from app.schemas.mensalidade import PRIMEIRO_MES_ACEITO, PagamentoEntrada

NUMERO_MAXIMO = 30
# Um vencimento mais de um ano depois da emissão é quase sempre erro de digitação no ano
PRAZO_MAXIMO_DO_VENCIMENTO = timedelta(days=366)


class NotaEntrada(BaseModel):
    """Dados da nota fiscal, que é emitida fora do sistema (RF31)."""

    numero_nota: str
    data_emissao: date
    data_vencimento: date

    @field_validator("numero_nota", mode="before")
    @classmethod
    def exige_numero(cls, valor: object) -> object:
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            raise ValueError("Informe o número da nota")
        return valor

    @field_validator("numero_nota")
    @classmethod
    def numero_limpo(cls, valor: str) -> str:
        texto = " ".join(texto_valido(valor).split())
        if len(texto) > NUMERO_MAXIMO:
            raise ValueError(f"Use no máximo {NUMERO_MAXIMO} caracteres no número da nota")
        return texto

    @field_validator("data_emissao", mode="before")
    @classmethod
    def exige_data_da_emissao(cls, valor: object) -> object:
        return exige_data(valor, "Informe a data de emissão da nota")

    @field_validator("data_emissao")
    @classmethod
    def emissao_possivel(cls, valor: date) -> date:
        # RN09: a nota já foi emitida, então a data não pode ser futura
        if valor > tempo.hoje():
            raise ValueError("A data de emissão não pode ser no futuro")
        if valor < PRIMEIRO_MES_ACEITO:
            raise ValueError("Essa data é antiga demais")
        return valor

    @field_validator("data_vencimento", mode="before")
    @classmethod
    def exige_data_do_vencimento(cls, valor: object) -> object:
        return exige_data(valor, "Informe o vencimento da cobrança")

    @field_validator("data_vencimento")
    @classmethod
    def vencimento_possivel(cls, valor: date, info: ValidationInfo) -> date:
        if valor < PRIMEIRO_MES_ACEITO:
            raise ValueError("Essa data é antiga demais")
        emissao = info.data.get("data_emissao")
        if emissao is not None:
            if valor < emissao:
                raise ValueError("O vencimento não pode ser antes da emissão da nota")
            if valor > emissao + PRAZO_MAXIMO_DO_VENCIMENTO:
                raise ValueError("O vencimento deve ser em até um ano depois da emissão")
        return valor


class PagamentoDaCobrancaEntrada(PagamentoEntrada):
    """Pagamento da empresa: as mesmas regras do pagamento de mensalidade, com outras formas."""

    forma_pagamento: FormaDePagamentoCobranca

    @field_validator("forma_pagamento", mode="before")
    @classmethod
    def forma_conhecida(cls, valor: object) -> object:
        if isinstance(valor, str) and valor in {forma.value for forma in FormaDePagamentoCobranca}:
            return valor
        raise ValueError("Escolha a forma de pagamento: PIX, transferência, boleto ou outra")


class PadrinhoDaCobranca(BaseModel):
    id: int
    nome: str
    ativo: bool


class ItemDaCobranca(BaseModel):
    """Um aluno apadrinhado dentro da cobrança, com o valor da mensalidade dele."""

    mensalidade_id: int
    matricula_id: int
    aluno: AlunoResumo
    valor: Decimal


class NotaLeitura(BaseModel):
    numero_nota: str
    data_emissao: date
    registrada_por: str
    registrada_em: datetime


class PagamentoDaCobrancaLeitura(BaseModel):
    data_pagamento: date
    valor_pago: Decimal
    forma_pagamento: FormaDePagamentoCobranca
    observacao: str | None
    registrado_por: str
    registrado_em: datetime


class PagamentoDaCobrancaCanceladoLeitura(PagamentoDaCobrancaLeitura):
    """Um pagamento da empresa que foi cancelado: continua visível, com o motivo (RF17)."""

    cancelamento: CancelamentoLeitura


class CobrancaLeitura(BaseModel):
    """Cobrança como a API devolve: a empresa, os alunos, a nota e a situação já calculada."""

    id: int
    padrinho: PadrinhoDaCobranca
    competencia: date
    valor: Decimal
    status: StatusCobranca
    situacao: SituacaoCobranca
    # Vale só para a cobrança "a emitir": a nota passou do prazo combinado com a empresa
    emissao_atrasada: bool
    # Prazo para emitir a nota, se a empresa combinou um
    limite_emissao: date | None
    data_vencimento: date
    dias_em_atraso: int
    alunos: list[ItemDaCobranca]
    gerada_por: str
    gerada_em: datetime
    nota: NotaLeitura | None = None
    pagamento: PagamentoDaCobrancaLeitura | None = None
    # Só a cobrança cancelada tem motivo, quem cancelou e quando
    motivo: str | None = None
    cancelada_por: str | None = None
    cancelada_em: datetime | None = None
    # Pagamentos cancelados desta cobrança, do mais recente para o mais antigo (RF17)
    pagamentos_cancelados: list[PagamentoDaCobrancaCanceladoLeitura] = []
