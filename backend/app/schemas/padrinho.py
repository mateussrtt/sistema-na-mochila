import re

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.schemas.comum import texto_valido

DIA_MINIMO = 1
# O dia 28 existe em todos os meses: a data combinada nunca cai fora do calendário
DIA_MAXIMO = 28

_CNPJ = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
_PESOS_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _digito(caracteres: str, pesos: tuple[int, ...]) -> int:
    # Cada caractere vale o seu código ASCII menos 48: "0" a "9" valem 0 a 9 e "A" a "Z" valem
    # 17 a 42. É a conta do CNPJ alfanumérico, que dá o mesmo resultado do CNPJ só com números
    soma = sum((ord(c) - 48) * p for c, p in zip(caracteres, pesos, strict=True))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_e_valido(cnpj: str) -> bool:
    """Confere os 14 caracteres e os dois dígitos verificadores (numérico ou alfanumérico)."""
    if not _CNPJ.match(cnpj) or len(set(cnpj)) == 1:
        return False
    primeiro = _digito(cnpj[:12], _PESOS_1)
    segundo = _digito(cnpj[:12] + str(primeiro), _PESOS_2)
    return cnpj[12:] == f"{primeiro}{segundo}"


def limpa_cnpj(texto: str) -> str:
    """Tira a máscara (pontos, barra, traço e espaços) e põe em maiúsculas."""
    return re.sub(r"[.\-/\s]", "", texto).upper()


class PadrinhoEntrada(BaseModel):
    """Dados enviados para cadastrar ou editar um padrinho (empresa)."""

    nome: str = Field(min_length=2, max_length=120)
    cnpj: str | None = None
    contato: str | None = Field(default=None, max_length=120)
    telefone: str = Field(max_length=20)
    email: EmailStr
    dia_vencimento: int
    emitir_ate_dia: int | None = None
    ativo: bool = True

    @model_validator(mode="before")
    @classmethod
    def contato_ausente_vira_vazio(cls, dados: object) -> object:
        # Os campos continuam obrigatórios (e assim saem no OpenAPI). Isto só faz o campo que nem
        # veio no corpo cair na mesma mensagem em português do campo em branco, em vez de
        # "Field required" em inglês
        if isinstance(dados, dict):
            return {"telefone": None, "email": None} | dados
        return dados

    @field_validator("nome", "contato", mode="before")
    @classmethod
    def limpa_espacos(cls, valor: object) -> object:
        return " ".join(valor.split()) if isinstance(valor, str) else valor

    @field_validator("cnpj", "contato", "emitir_ate_dia", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, valor: object) -> object:
        # Só o texto em branco vira "sem valor". Um 0, um {} ou um false continuam como vieram,
        # para a validação do campo recusá-los em vez de apagá-los em silêncio
        if isinstance(valor, str):
            return valor.strip() or None
        return valor

    @field_validator("ativo", mode="before")
    @classmethod
    def ativo_e_verdadeiro_ou_falso(cls, valor: object) -> object:
        # O padrão do pydantic aceita 0, 1 e textos como "no" ou "off" como verdadeiro/falso:
        # aqui só vale true ou false, para um valor torto não inativar o padrinho sem querer
        if not isinstance(valor, bool):
            raise ValueError("Informe verdadeiro ou falso")
        return valor

    @field_validator("telefone", "email", mode="before")
    @classmethod
    def contato_obrigatorio(cls, valor: object, info: ValidationInfo) -> object:
        # Telefone e e-mail são obrigatórios (a empresa precisa poder ser procurada)
        if isinstance(valor, str):
            valor = valor.strip()
        if valor is None or valor == "":
            nome = "o telefone" if info.field_name == "telefone" else "o e-mail"
            raise ValueError(f"Informe {nome} de contato")
        return valor

    @field_validator("dia_vencimento", "emitir_ate_dia", mode="before")
    @classmethod
    def dia_nao_e_verdadeiro_ou_falso(cls, valor: object) -> object:
        # Em Python, True vale 1: sem isso, "true" seria aceito como dia 1
        if isinstance(valor, bool):
            raise ValueError("Informe o dia como um número")
        return valor

    @field_validator("nome", "contato", "telefone", "cnpj")
    @classmethod
    def sem_caractere_invalido(cls, valor: str | None) -> str | None:
        return texto_valido(valor)

    @field_validator("telefone")
    @classmethod
    def valida_telefone(cls, valor: str) -> str:
        if len(re.sub(r"\D", "", valor)) not in (10, 11):
            raise ValueError("Telefone deve ter DDD e 8 ou 9 dígitos")
        return valor

    @field_validator("cnpj")
    @classmethod
    def valida_cnpj(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        cnpj = limpa_cnpj(valor)
        if not cnpj_e_valido(cnpj):
            raise ValueError("CNPJ inválido. Confira os números")
        return cnpj

    @field_validator("dia_vencimento")
    @classmethod
    def dia_do_vencimento(cls, valor: int) -> int:
        if not DIA_MINIMO <= valor <= DIA_MAXIMO:
            raise ValueError(f"Use um dia de {DIA_MINIMO} a {DIA_MAXIMO}")
        return valor

    @field_validator("emitir_ate_dia")
    @classmethod
    def dia_da_nota(cls, valor: int | None, info: ValidationInfo) -> int | None:
        if valor is None:
            return None
        if not DIA_MINIMO <= valor <= DIA_MAXIMO:
            raise ValueError(f"Use um dia de {DIA_MINIMO} a {DIA_MAXIMO}")
        vencimento = info.data.get("dia_vencimento")
        if vencimento is not None and valor > vencimento:
            raise ValueError("A nota deve ser emitida até o dia do vencimento, no máximo")
        return valor


class PadrinhoLeitura(BaseModel):
    """Padrinho como a API devolve. O CNPJ vai sem máscara."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str | None
    contato: str | None
    telefone: str
    email: str
    dia_vencimento: int
    emitir_ate_dia: int | None
    ativo: bool
    # Alunos com matrícula ativa apadrinhados por esta empresa (para avisar antes de inativar)
    alunos_apadrinhados: int = 0
