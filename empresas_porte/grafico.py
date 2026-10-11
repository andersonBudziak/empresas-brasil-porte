"""Gráfico de abertura, fechamento e saldo por porte, com as cores da bandeira."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from empresas_porte.dados import NOMES_PORTE, PORTES  # noqa: E402
from empresas_porte.formatacao import abreviar, formatar_numero  # noqa: E402

# Paleta inspirada na bandeira, validada para daltonismo (protan/deutan/tritan).
VERDE = "#00873A"  # abertas
VERDE_CLARO = "#8CCBA4"  # abertas de 2025 (outro relatório)
AMARELO = "#E5A800"  # fechadas
AZUL = "#1F4FA3"  # saldo
TINTA = "#1B1B1B"
TINTA_SECUNDARIA = "#55534E"
TINTA_SUAVE = "#898781"
GRADE = "#E1E0D9"
FUNDO = "#FCFCFB"

LARGURA_BARRA = 0.38


def _eixo_milhar(valor: float, _pos: int) -> str:
    """Rótulo de eixo enxuto: "4 mi", "2,5 mi", "500 mil"."""
    if not valor:
        return "0"
    if abs(valor) >= 1_000_000:
        mi = valor / 1_000_000
        casas = 0 if mi == int(mi) else 1
        return f"{formatar_numero(mi, casas)} mi"
    return abreviar(valor)


def _desenhar_porte(
    ax: plt.Axes, dados_porte: pd.DataFrame, titulo: str, rotular_fechadas: bool = True
) -> None:
    anos = dados_porte["ano"].to_numpy()
    x = np.arange(len(anos))
    abertas = dados_porte["abertas"].astype(float).to_numpy()
    fechadas = dados_porte["fechadas"].astype(float).to_numpy()
    saldo = dados_porte["saldo"].astype(float).to_numpy()
    sem_fechamento = np.isnan(fechadas)

    cores_abertas = [VERDE_CLARO if s else VERDE for s in sem_fechamento]
    hachura = ["////" if s else "" for s in sem_fechamento]
    barras = ax.bar(
        x - LARGURA_BARRA / 2 - 0.01, abertas, LARGURA_BARRA,
        color=cores_abertas, edgecolor=FUNDO, linewidth=0, zorder=2,
    )
    for barra, h in zip(barras, hachura):
        if h:
            barra.set_hatch(h)
            barra.set_edgecolor(VERDE)
            barra.set_linewidth(0)

    ax.bar(
        x + LARGURA_BARRA / 2 + 0.01, np.nan_to_num(fechadas), LARGURA_BARRA,
        color=AMARELO, zorder=2,
    )
    ax.plot(
        x[~sem_fechamento], saldo[~sem_fechamento],
        color=AZUL, linewidth=2, linestyle=(0, (4, 3)), marker="o", markersize=5,
        markeredgecolor=FUNDO, markeredgewidth=1.5, zorder=3,
    )

    # Rótulos diretos só no último ano completo e no ano parcial.
    topo = np.nanmax(abertas)
    for i in range(len(anos)):
        if anos[i] < anos.max() - 1:
            continue
        ax.text(x[i] - LARGURA_BARRA / 2, abertas[i] + topo * 0.02, abreviar(abertas[i]),
                ha="center", va="bottom", fontsize=8, color=TINTA_SECUNDARIA)
        if sem_fechamento[i]:
            ax.text(x[i] + LARGURA_BARRA / 2, topo * 0.02, "não\ndivulgado",
                    ha="center", va="bottom", fontsize=7, color=TINTA_SUAVE, linespacing=1.1)
        elif rotular_fechadas:
            ax.text(x[i] + LARGURA_BARRA / 2, fechadas[i] + topo * 0.02, abreviar(fechadas[i]),
                    ha="center", va="bottom", fontsize=8, color=TINTA_SECUNDARIA)

    ax.set_title(titulo, loc="left", fontsize=11, color=TINTA, fontweight="bold", pad=8)
    ax.set_xticks(x, [str(a) for a in anos])
    ax.set_ylim(0, topo * 1.14)
    ax.set_xlim(-0.6, len(anos) - 0.3)
    ax.yaxis.set_major_formatter(FuncFormatter(_eixo_milhar))
    ax.grid(axis="y", color=GRADE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color("#C3C2B7")
    ax.tick_params(axis="both", colors=TINTA_SUAVE, labelsize=9, length=0)
    ax.set_facecolor(FUNDO)


def _salvar(fig: plt.Figure, destino: Path, nome: str) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    arquivos = []
    for ext in ("png", "svg"):
        caminho = destino / f"{nome}.{ext}"
        fig.savefig(caminho, dpi=200, facecolor=FUNDO)
        arquivos.append(caminho)
    plt.close(fig)
    return arquivos


def gerar_grafico_total(dados: pd.DataFrame, destino: Path) -> list[Path]:
    """Todas as empresas do país (todos os portes), segundo o Mapa de Empresas."""
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(11, 6.2), facecolor=FUNDO)
    ax = fig.add_axes([0.08, 0.17, 0.90, 0.63])

    anos = dados["ano"].to_numpy()
    x = np.arange(len(anos))
    abertas = dados["abertas"].to_numpy(dtype=float)
    fechadas = dados["fechadas"].to_numpy(dtype=float)
    saldo = dados["saldo"].to_numpy(dtype=float)

    ax.bar(x - LARGURA_BARRA / 2 - 0.01, abertas, LARGURA_BARRA, color=VERDE, zorder=2)
    ax.bar(x + LARGURA_BARRA / 2 + 0.01, fechadas, LARGURA_BARRA, color=AMARELO, zorder=2)
    ax.plot(x, saldo, color=AZUL, linewidth=2, linestyle=(0, (4, 3)), marker="o",
            markersize=5, markeredgecolor=FUNDO, markeredgewidth=1.5, zorder=3)

    topo = abertas.max()
    for i in range(len(anos)):
        ax.text(x[i] - LARGURA_BARRA / 2, abertas[i] + topo * 0.02, abreviar(abertas[i]),
                ha="center", va="bottom", fontsize=8, color=TINTA_SECUNDARIA)
        ax.text(x[i] + LARGURA_BARRA / 2, fechadas[i] + topo * 0.02, abreviar(fechadas[i]),
                ha="center", va="bottom", fontsize=8, color=TINTA_SECUNDARIA)

    ax.set_xticks(x, [str(a) for a in anos])
    ax.set_xlim(-0.6, len(anos) - 0.4)
    ax.set_ylim(0, topo * 1.12)
    ax.yaxis.set_major_formatter(FuncFormatter(_eixo_milhar))
    ax.grid(axis="y", color=GRADE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color("#C3C2B7")
    ax.tick_params(axis="both", colors=TINTA_SUAVE, labelsize=9, length=0)
    ax.set_facecolor(FUNDO)

    fig.text(0.08, 0.935, "Todas as empresas: abertas e fechadas no Brasil",
             fontsize=16, color=TINTA, fontweight="bold")
    fig.text(0.08, 0.885,
             f"{anos.min()} a {anos.max()} · todos os portes e classes (MEI, ME, EPP, médias e "
             "grandes), matrizes e filiais",
             fontsize=10.5, color=TINTA_SECUNDARIA)
    legenda = [
        Patch(facecolor=VERDE, label="Abertas"),
        Patch(facecolor=AMARELO, label="Fechadas"),
        Line2D([0], [0], color=AZUL, linewidth=2, linestyle=(0, (4, 3)), marker="o",
               markersize=5, label="Saldo (abertas − fechadas)"),
    ]
    fig.legend(handles=legenda, loc="upper left", bbox_to_anchor=(0.075, 0.865), ncol=3,
               frameon=False, fontsize=9, labelcolor=TINTA_SECUNDARIA, handlelength=1.6,
               columnspacing=1.6)
    fig.text(0.08, 0.04,
             "Fonte: Mapa de Empresas (Governo Federal), boletins do 3º quadrimestre de cada ano. "
             "2024: totais do boletim reproduzidos pelo Diário do Comércio.\n"
             "Metodologia diferente da do Sebrae: os totais não se comparam diretamente com o "
             "gráfico por porte. 2025 fica de fora: o boletim com o total anual não foi localizado.",
             fontsize=8, color=TINTA_SUAVE, linespacing=1.5)
    return _salvar(fig, destino, "todas_empresas_abertas_fechadas")


def gerar_grafico(dados: pd.DataFrame, destino: Path) -> list[Path]:
    """Desenha o gráfico e salva em PNG e SVG. Retorna os caminhos gerados."""
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(11, 9), facecolor=FUNDO)
    grade = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], hspace=0.38, wspace=0.18,
                             left=0.07, right=0.98, top=0.83, bottom=0.11)
    eixos = [fig.add_subplot(grade[0, :]), fig.add_subplot(grade[1, 0]), fig.add_subplot(grade[1, 1])]

    for ax, porte in zip(eixos, PORTES):
        # Nos painéis estreitos o rótulo das fechadas colide com a barra vizinha;
        # os valores completos ficam na tabela gerada junto.
        _desenhar_porte(ax, dados[dados["porte"] == porte], NOMES_PORTE[porte],
                        rotular_fechadas=(porte == "MEI"))

    fig.text(0.07, 0.962, "Empresas abertas e fechadas no Brasil, por porte",
             fontsize=16, color=TINTA, fontweight="bold")
    ano_ini, ano_fim = int(dados["ano"].min()), int(dados["ano"].max())
    fig.text(0.07, 0.933,
             f"{ano_ini} a {ano_fim} · inscrições e baixas de CNPJ (matrizes e filiais)",
             fontsize=10.5, color=TINTA_SECUNDARIA)

    legenda = [
        Patch(facecolor=VERDE, label="Abertas"),
        Patch(facecolor=VERDE_CLARO, edgecolor=VERDE, hatch="////", linewidth=0,
              label="Abertas em 2025 (relatório anual de 2025)"),
        Patch(facecolor=AMARELO, label="Fechadas (baixas)"),
        Line2D([0], [0], color=AZUL, linewidth=2, linestyle=(0, (4, 3)), marker="o",
               markersize=5, label="Saldo (abertas − fechadas)"),
    ]
    fig.legend(handles=legenda, loc="upper left", bbox_to_anchor=(0.065, 0.918), ncol=4,
               frameon=False, fontsize=9, labelcolor=TINTA_SECUNDARIA, handlelength=1.6,
               columnspacing=1.6)

    fig.text(0.07, 0.045,
             "Fonte: Sebrae, com base no Cartão CNPJ da Receita Federal. 2019–2024: estudo "
             "\"Análise de Abertura e Fechamento de Empresas\" (mai/2025), Tabela A.1.\n"
             "2025: \"Abertura de Pequenos Negócios – Anual 2025\" (jan/2026); MEI arredondado "
             "em 3,81 mi; fechamentos de 2025 por porte ainda não divulgados.",
             fontsize=8, color=TINTA_SUAVE, linespacing=1.5)

    return _salvar(fig, destino, "empresas_abertas_fechadas_por_porte")
