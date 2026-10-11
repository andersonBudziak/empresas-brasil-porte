"""Formatação de números no padrão brasileiro (1.234.567 e "1,2 mi")."""

from __future__ import annotations

import math


def formatar_numero(valor: float | int | None, casas: int = 0) -> str:
    """Formata com ponto como separador de milhar e vírgula decimal.

    >>> formatar_numero(1234567)
    '1.234.567'
    >>> formatar_numero(1234.5, casas=1)
    '1.234,5'
    """
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def abreviar(valor: float | int | None) -> str:
    """Abrevia em "mil" e "mi", como se lê em jornal brasileiro.

    >>> abreviar(3_145_705)
    '3,15 mi'
    >>> abreviar(530_222)
    '530 mil'
    >>> abreviar(950)
    '950'
    """
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    absoluto = abs(valor)
    sinal = "-" if valor < 0 else ""
    if absoluto >= 1_000_000:
        return f"{sinal}{formatar_numero(absoluto / 1_000_000, 2)} mi"
    if absoluto >= 1_000:
        return f"{sinal}{formatar_numero(round(absoluto / 1_000))} mil"
    return f"{sinal}{formatar_numero(absoluto)}"
