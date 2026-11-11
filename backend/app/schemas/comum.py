"""Validações usadas por mais de um cadastro."""

from decimal import Decimal, InvalidOperation

# Maior valor que cabe no inteiro do banco (id). Acima disso o PostgreSQL daria erro 500
ID_MAXIMO = 2_147_483_647


def texto_valido(valor: str | None) -> str | None:
    """Recusa o caractere nulo (\\x00) e pedaços soltos de Unicode (como "\\ud800").

    O PostgreSQL não aceita nenhum dos dois em texto. Sem esta checagem, a gravação no banco
    falharia e viraria erro 500.
    """
    if valor is None:
        return None
    if "\x00" in valor:
        raise ValueError("O texto tem um caractere inválido")
    try:
        valor.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("O texto tem um caractere inválido") from None
    return valor


def ler_dinheiro(valor: object, mensagem_vazio: str) -> Decimal:
    """Lê um valor em reais digitado como número ou texto (aceita vírgula).

    Vazio vira a mensagem em português informada; texto que não é número e `NaN`/`Infinity`
    (que quebrariam a resposta de erro em JSON) viram "Informe um valor válido".
    """
    if isinstance(valor, str):
        valor = valor.strip().replace(",", ".")
    if valor is None or valor == "":
        raise ValueError(mensagem_vazio)
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        raise ValueError("Informe um valor válido") from None
    if not numero.is_finite():
        raise ValueError("Informe um valor válido")
    return numero


def conferir_dinheiro(valor: Decimal, nome: str) -> Decimal:
    """Confere um valor em reais: maior que zero (RN09), até 2 casas e abaixo de 100 milhões.

    `nome` entra nas mensagens ("O valor da despesa deve ser maior que zero"). Devolve o valor
    com exatamente 2 casas (RNF08).
    """
    if valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero")
    if valor.as_tuple().exponent < -2:
        raise ValueError("Use no máximo 2 casas decimais")
    if valor >= Decimal(10) ** 8:
        raise ValueError(f"{nome} é alto demais")
    return valor.quantize(Decimal("0.01"))


def termo_de_busca(busca: str | None) -> str:
    """Limpa o texto digitado na busca. O caractere nulo é descartado."""
    return busca.replace("\x00", "").strip() if busca else ""
