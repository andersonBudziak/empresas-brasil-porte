"""Gráfico único: todas as empresas desde 2010, com o porte empilhado a partir de 2019.

Abertas ficam acima do eixo e fechadas abaixo. Até 2018 só existe o total (Mapa de
Empresas); de 2019 em diante as barras mostram MEI, ME e EPP (Sebrae) empilhados, e
um traço marca o total do Mapa de Empresas no mesmo ano. As duas fontes têm
metodologias diferentes, então a soma dos portes não precisa bater com o traço.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from empresas_porte.dados import PORTES, rotulo_ano  # noqa: E402
from empresas_porte.formatacao import abreviar  # noqa: E402
from empresas_porte.grafico import (  # noqa: E402
    AMARELO, AZUL, FUNDO, GRADE, TINTA, TINTA_SECUNDARIA, TINTA_SUAVE, VERDE,
    _eixo_milhar, _salvar,
)

CORES_PORTE = {"MEI": VERDE, "ME": AZUL, "EPP": AMARELO}
CINZA_TOTAL = "#B4B2A9"
FAIXA_PORTE = "#EEF0EA"
ANO_PORTE = 2019
EVENTOS_CURTOS = {2015: "LC 147/2014", 2018: "cancelamento\nem massa\nde MEI"}


@dataclass
class SerieCombinada:
    """Uma linha por ano, já no formato que os dois gráficos (PNG e HTML) desenham."""

    anos: list[int]
    total_abertas: list[float | None]  # Mapa de Empresas
    total_fechadas: list[float | None]
    total_saldo: list[float | None]
    total_aprox: list[bool]
    porte_abertas: dict[str, list[float | None]] = field(default_factory=dict)  # Sebrae
    porte_fechadas: dict[str, list[float | None]] = field(default_factory=dict)
    porte_aprox: list[bool] = field(default_factory=list)
    periodo: list[str] = field(default_factory=list)  # "ano" ou ano parcial, ex.: "jan-set"

    def parcial(self, i: int) -> bool:
        return self.periodo[i] != "ano"

    def rotulos(self, quebra: str = "\n") -> list[str]:
        return [rotulo_ano(a, p, quebra) for a, p in zip(self.anos, self.periodo)]

    def tem_porte(self, i: int) -> bool:
        return self.porte_abertas["MEI"][i] is not None

    def abertas_da_barra(self, i: int) -> float | None:
        """O número escrito sobre a barra: a soma do que ela mostra."""
        if self.tem_porte(i):
            return float(sum(self.porte_abertas[p][i] for p in PORTES))
        return self.total_abertas[i]

    def fechadas_da_barra(self, i: int) -> float | None:
        if self.tem_porte(i):
            vals = [self.porte_fechadas[p][i] for p in PORTES]
            return None if any(v is None for v in vals) else float(sum(vals))
        return self.total_fechadas[i]


def _ou_none(v) -> float | None:
    return None if pd.isna(v) else float(v)


def montar_serie(porte: pd.DataFrame, todas: pd.DataFrame) -> SerieCombinada:
    anos = sorted(set(todas["ano"].astype(int)) | set(porte["ano"].astype(int)))
    t = todas.set_index("ano")
    serie = SerieCombinada(
        anos=anos,
        total_abertas=[_ou_none(t["abertas"].get(a)) for a in anos],
        total_fechadas=[_ou_none(t["fechadas"].get(a)) for a in anos],
        total_saldo=[_ou_none(t["saldo"].get(a)) for a in anos],
        total_aprox=[bool(t["abertas_aproximado"].get(a, False) or t["fechadas_aproximado"].get(a, False))
                     for a in anos],
    )
    for p in PORTES:
        d = porte[porte["porte"] == p].set_index("ano")
        serie.porte_abertas[p] = [_ou_none(d["abertas"].get(a)) for a in anos]
        serie.porte_fechadas[p] = [_ou_none(d["fechadas"].get(a)) for a in anos]
    mei = porte[porte["porte"] == "MEI"].set_index("ano")
    serie.porte_aprox = [bool(mei["abertas_aproximado"].get(a, False)) for a in anos]
    serie.periodo = [str(mei["periodo"].get(a, "ano")) if "periodo" in mei else "ano" for a in anos]
    return serie


def gerar_grafico_combinado(serie: SerieCombinada, destino: Path) -> list[Path]:
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(14, 8.4), facecolor=FUNDO)
    ax = fig.add_axes([0.065, 0.155, 0.92, 0.645])
    x = np.arange(len(serie.anos))
    larg = 0.66

    for i, ano in enumerate(serie.anos):
        if serie.tem_porte(i):
            sem_fech = serie.fechadas_da_barra(i) is None
            base_a = base_f = 0.0
            parcial = serie.parcial(i)
            for p in PORTES:
                a = serie.porte_abertas[p][i]
                barra = ax.bar(x[i], a, larg, bottom=base_a, color=CORES_PORTE[p],
                               alpha=0.45 if sem_fech else 1, edgecolor=FUNDO, linewidth=1,
                               zorder=2)[0]
                if parcial:
                    # Ano incompleto: hachura para não parecer um ano inteiro.
                    barra.set_hatch("////")
                    barra.set_edgecolor(CORES_PORTE[p])
                    barra.set_linewidth(0)
                base_a += a
                f = serie.porte_fechadas[p][i]
                if f is not None:
                    ax.bar(x[i], -f, larg, bottom=-base_f, color=CORES_PORTE[p],
                           edgecolor=FUNDO, linewidth=1, zorder=2)
                    base_f += f
            if sem_fech:
                ax.text(x[i], -0.1e6, "fechadas\nnão\ndivulgadas", ha="center", va="top",
                        fontsize=7, color=TINTA_SUAVE, linespacing=1.1)
            ta, tf = serie.total_abertas[i], serie.total_fechadas[i]
            for alvo in (ta, None if tf is None else -tf):
                if alvo is not None:
                    ax.plot([x[i] - larg / 2 - 0.07, x[i] + larg / 2 + 0.07], [alvo, alvo],
                            color=TINTA, linewidth=1.6, zorder=4, solid_capstyle="butt")
        else:
            ax.bar(x[i], serie.total_abertas[i], larg, color=CINZA_TOTAL, zorder=2)
            ax.bar(x[i], -serie.total_fechadas[i], larg, color=CINZA_TOTAL, zorder=2)

        # Quantas abriram: número sobre cada barra (acima do traço do total, se houver).
        abertas = serie.abertas_da_barra(i)
        topo = max(abertas, serie.total_abertas[i] or 0)
        rotulo = abreviar(abertas) + ("*" if serie.porte_aprox[i] else "")
        ax.text(x[i], topo + 0.07e6, rotulo, ha="center", va="bottom", fontsize=8.5,
                color=TINTA, zorder=6)

    validos = [(xi, s) for xi, s in zip(x, serie.total_saldo) if s is not None]
    ax.plot([v[0] for v in validos], [v[1] for v in validos], color=TINTA, linewidth=1.8,
            linestyle=(0, (4, 3)), marker="o", markersize=4, markerfacecolor=TINTA,
            markeredgecolor=FUNDO, markeredgewidth=1.2, zorder=5)
    ax.axhline(0, color="#8a8880", linewidth=1, zorder=3)

    i_porte = serie.anos.index(ANO_PORTE)
    ax.axvspan(x[i_porte] - 0.5, x[-1] + 0.5, color=FAIXA_PORTE, zorder=0)
    ax.text(x[i_porte] - 0.42, 5.25e6, "a partir de 2019: detalhe por porte (Sebrae)",
            fontsize=8.5, color=TINTA_SECUNDARIA, va="top")
    for ano, texto in EVENTOS_CURTOS.items():
        i = serie.anos.index(ano)
        ax.text(x[i], -serie.total_fechadas[i] - 0.08e6, texto,
                ha="center", va="top", fontsize=7, color=TINTA_SECUNDARIA, linespacing=1.1)

    ax.set_xticks(x, serie.rotulos())
    ax.set_xlim(-0.6, len(serie.anos) - 0.4)
    ax.set_ylim(-3.35e6, 5.3e6)
    ax.grid(axis="y", color=GRADE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="both", colors=TINTA_SUAVE, labelsize=9, length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: _eixo_milhar(abs(v), p)))
    ax.set_facecolor(FUNDO)
    ax.text(-0.55, 4.72e6, "▲ abertas", fontsize=9, color=TINTA_SECUNDARIA)
    ax.text(-0.55, -3.2e6, "▼ fechadas", fontsize=9, color=TINTA_SECUNDARIA)

    fig.text(0.065, 0.955, "Empresas abertas e fechadas no Brasil, por porte",
             fontsize=17, color=TINTA, fontweight="bold")
    fig.text(0.065, 0.922,
             f"{serie.anos[0]} a {serie.rotulos(' ')[-1]} · abertas acima do eixo, fechadas abaixo. "
             "O número sobre cada barra é quantas empresas abriram no ano.",
             fontsize=10.5, color=TINTA_SECUNDARIA)
    legenda = [
        Patch(facecolor=CINZA_TOTAL, label="Todas as empresas (até 2018)"),
        Patch(facecolor=VERDE, label="MEI"), Patch(facecolor=AZUL, label="Microempresa (ME)"),
        Patch(facecolor=AMARELO, label="Pequeno porte (EPP)"),
        Patch(facecolor="#BFDDC9", edgecolor=VERDE, hatch="////", linewidth=0,
              label="Ano parcial"),
        Line2D([0], [0], color=TINTA, linewidth=1.6, label="Total do governo (traço)"),
        Line2D([0], [0], color=TINTA, linewidth=1.8, linestyle=(0, (4, 3)), marker="o",
               markersize=4, label="Saldo de todas as empresas"),
    ]
    fig.legend(handles=legenda, loc="upper left", bbox_to_anchor=(0.06, 0.905), ncol=7,
               frameon=False, fontsize=9, labelcolor=TINTA_SECUNDARIA, handlelength=1.6,
               columnspacing=1.3)
    fig.text(0.065, 0.018,
             "Fontes: até 2018 e traço = Mapa de Empresas (Governo Federal); MEI, ME e EPP = Sebrae, "
             "com base no CNPJ da Receita Federal. 2010–2019 do total arredondados em dezenas de milhar.\n"
             "As fontes têm metodologias diferentes: a soma dos portes não precisa bater com o traço. "
             "2025: só aberturas (relatório anual do Sebrae).\n"
             "2026: janeiro a setembro, só aberturas; total exato (4.391.539) e porte estimado pelos "
             "percentuais divulgados (77% MEI, 19% ME, 4% EPP). * = valor aproximado ou estimado.",
             fontsize=8, color=TINTA_SUAVE, linespacing=1.5)
    return _salvar(fig, destino, "empresas_abertas_fechadas_combinado")
