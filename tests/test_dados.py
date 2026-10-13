"""Confere os dados contra os totais publicados pela fonte.

Os totais de Pequenos Negócios (MEI + ME + EPP) abaixo foram copiados da
Tabela A.1 do estudo do Sebrae (2019–2024). Se alguém digitar um número
errado no CSV, a soma deixa de bater e o teste falha.
"""

import pandas as pd
import pytest

from empresas_porte import (
    abreviar, carregar_dados, carregar_fontes, carregar_todas_empresas, formatar_numero,
)

TOTAL_PN_ABERTAS = {
    2019: 3_100_898, 2020: 3_294_280, 2021: 3_943_584,
    2022: 3_752_347, 2023: 3_782_268, 2024: 4_160_645,
}
TOTAL_PN_FECHADAS = {
    2019: 1_160_101, 2020: 1_043_052, 2021: 1_418_214,
    2022: 1_676_183, 2023: 2_131_117, 2024: 2_395_523,
}
# Saldo do MEI publicado na Tabela A.3 do mesmo estudo.
SALDO_MEI = {
    2019: 1_758_960, 2020: 2_023_778, 2021: 2_165_044,
    2022: 1_731_424, 2023: 1_273_113, 2024: 1_345_546,
}


@pytest.fixture(scope="module")
def dados() -> pd.DataFrame:
    return carregar_dados()


@pytest.mark.parametrize("ano", sorted(TOTAL_PN_ABERTAS))
def test_soma_dos_portes_bate_com_total_publicado(dados, ano):
    do_ano = dados[dados["ano"] == ano]
    assert int(do_ano["abertas"].sum()) == TOTAL_PN_ABERTAS[ano]
    assert int(do_ano["fechadas"].sum()) == TOTAL_PN_FECHADAS[ano]


@pytest.mark.parametrize("ano", sorted(SALDO_MEI))
def test_saldo_mei_bate_com_tabela_a3(dados, ano):
    linha = dados[(dados["ano"] == ano) & (dados["porte"] == "MEI")].iloc[0]
    assert int(linha["saldo"]) == SALDO_MEI[ano]


def test_2025_sem_fechamento_nem_saldo(dados):
    d2025 = dados[dados["ano"] == 2025]
    assert len(d2025) == 3
    assert d2025["fechadas"].isna().all()
    assert d2025["saldo"].isna().all()


def test_toda_linha_aponta_para_fonte_existente(dados):
    fontes = carregar_fontes()
    usadas = set(dados["fonte_abertas"].dropna()) | set(dados["fonte_fechadas"].dropna())
    assert usadas <= set(fontes.index)
    assert fontes["url"].str.startswith("https://").all()


def test_formatacao_brasileira():
    assert formatar_numero(3_145_705) == "3.145.705"
    assert formatar_numero(1234.5, casas=1) == "1.234,5"
    assert abreviar(3_145_705) == "3,15 mi"
    assert abreviar(530_222) == "530 mil"
    assert abreviar(-43_032) == "-43 mil"


# Saldos anuais publicados nos boletins do Mapa de Empresas.
SALDO_TODAS = {
    2020: 2_315_054, 2021: 2_615_906, 2022: 2_142_300,
    2023: 1_714_847, 2024: 1_818_713,
}


@pytest.mark.parametrize("ano", sorted(SALDO_TODAS))
def test_saldo_todas_empresas_bate_com_mapa(ano):
    todas = carregar_todas_empresas()
    linha = todas[todas["ano"] == ano].iloc[0]
    assert int(linha["saldo"]) == SALDO_TODAS[ano]
    assert linha["fonte"] in set(carregar_fontes().index)


def test_serie_longa_comeca_em_2010_e_marca_aproximados():
    todas = carregar_todas_empresas()
    assert todas["ano"].min() == 2010
    antigos = todas[todas["ano"] < 2019]
    assert antigos["abertas_aproximado"].all() and antigos["fechadas_aproximado"].all()
    assert not todas[todas["ano"] >= 2020]["fechadas_aproximado"].any()


def test_relatorio_html_tem_dados_e_fontes(tmp_path):
    from empresas_porte.relatorio import gerar_relatorio_html

    caminho = gerar_relatorio_html(
        carregar_dados(), carregar_todas_empresas(), carregar_fontes(), tmp_path
    )
    texto = caminho.read_text(encoding="utf-8")
    assert '<html lang="pt-BR">' in texto
    assert "{{" not in texto  # nenhum marcador sem substituir
    assert "4.254.903" in texto and "3.145.705" in texto
    for url in carregar_fontes()["url"]:
        assert url in texto


def test_serie_combinada_usa_total_ate_2018_e_porte_depois():
    from empresas_porte.combinado import montar_serie

    serie = montar_serie(carregar_dados(), carregar_todas_empresas())
    i2018, i2024, i2025 = (serie.anos.index(a) for a in (2018, 2024, 2025))
    assert not serie.tem_porte(i2018)
    assert serie.abertas_da_barra(i2018) == 2_630_000
    assert serie.abertas_da_barra(i2024) == TOTAL_PN_ABERTAS[2024]
    assert serie.fechadas_da_barra(i2024) == TOTAL_PN_FECHADAS[2024]
    assert serie.fechadas_da_barra(i2025) is None
    assert serie.porte_aprox[i2025]


def test_2026_parcial_soma_o_total_divulgado():
    d = carregar_dados()
    d2026 = d[d["ano"] == 2026]
    assert set(d2026["periodo"]) == {"jan-set"} and d2026["parcial"].all()
    assert int(d2026["abertas"].sum()) == 4_391_539  # Sebrae, acumulado jan–set/2026
    assert d2026["abertas_aproximado"].all()  # porte estimado pelos percentuais
    assert d2026["fechadas"].isna().all()
    assert not d[d["ano"] < 2026]["parcial"].any()
