"""Validações usadas por mais de um cadastro."""

# Maior valor que cabe no inteiro do banco (id). Acima disso o PostgreSQL daria erro 500
ID_MAXIMO = 2_147_483_647


def texto_valido(valor: str | None) -> str | None:
    """Recusa o caractere nulo (\\x00), que o PostgreSQL não aceita em texto.

    Sem esta checagem, a gravação no banco falharia e viraria erro 500.
    """
    if valor is not None and "\x00" in valor:
        raise ValueError("O texto tem um caractere inválido")
    return valor


def termo_de_busca(busca: str | None) -> str:
    """Limpa o texto digitado na busca. O caractere nulo é descartado."""
    return busca.replace("\x00", "").strip() if busca else ""
