"""Leitura dos dados e das fontes versionados em `dados/`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PASTA_DADOS = Path(__file__).resolve().parent.parent / "dados"
ARQUIVO_DADOS = PASTA_DADOS / "abertura_fechamento_por_porte.csv"
ARQUIVO_FONTES = PASTA_DADOS / "fontes.csv"
ARQUIVO_TODAS = PASTA_DADOS / "todas_empresas.csv"

PORTES = ["MEI", "ME", "EPP"]
NOMES_PORTE = {
    "MEI": "Microempreendedor individual (MEI)",
    "ME": "Microempresa (ME)",
    "EPP": "Empresa de pequeno porte (EPP)",
}


def carregar_dados(caminho: Path = ARQUIVO_DADOS) -> pd.DataFrame:
    """Retorna uma linha por ano e porte, com a coluna `saldo` calculada.

    `fechadas` e `saldo` ficam vazios (NA) nos anos em que o fechamento
    por porte ainda não foi divulgado.
    """
    df = pd.read_csv(
        caminho,
        dtype={"porte": "string", "fonte_abertas": "string", "fonte_fechadas": "string"},
    )
    df["fechadas"] = df["fechadas"].astype("Int64")
    df["abertas"] = df["abertas"].astype("Int64")
    df["abertas_aproximado"] = df["abertas_aproximado"].astype(bool)
    df["saldo"] = df["abertas"] - df["fechadas"]
    df["porte"] = pd.Categorical(df["porte"], categories=PORTES, ordered=True)
    return df.sort_values(["porte", "ano"]).reset_index(drop=True)


def carregar_fontes(caminho: Path = ARQUIVO_FONTES) -> pd.DataFrame:
    """Retorna a tabela de fontes, indexada pelo `id` usado em `dados`."""
    return pd.read_csv(caminho).set_index("id")


def carregar_todas_empresas(caminho: Path = ARQUIVO_TODAS) -> pd.DataFrame:
    """Totais anuais de todas as empresas (todos os portes), do Mapa de Empresas.

    De 2010 a 2019 os valores vêm de um gráfico do boletim com rótulos em milhões
    e duas casas decimais (precisão de 10 mil); as colunas `*_aproximado` marcam isso.
    """
    df = pd.read_csv(caminho, dtype={"fonte": "string"})
    for col in ("abertas_aproximado", "fechadas_aproximado"):
        df[col] = df[col].astype(bool)
    df["saldo"] = df["abertas"] - df["fechadas"]
    return df.sort_values("ano").reset_index(drop=True)
