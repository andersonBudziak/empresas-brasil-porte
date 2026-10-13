"""Testa o processamento da base de CNPJ com uma amostra sintética no layout da Receita.

Os arquivos imitam os originais: CSV dentro de zip, separador ';', campos entre aspas,
codificação latin-1, sem cabeçalho e datas AAAAMMDD.
"""

import zipfile

import pytest

pytest.importorskip("duckdb")

from empresas_porte.receita import COLUNAS_EMPRESAS, COLUNAS_ESTAB, COLUNAS_SIMPLES, processar


def _linha(valores: dict, colunas: list[str]) -> str:
    return ";".join(f'"{valores.get(c, "")}"' for c in colunas)


def _zip(pasta, nome_zip, nome_csv, linhas):
    with zipfile.ZipFile(pasta / nome_zip, "w") as z:
        z.writestr(nome_csv, ("\n".join(linhas) + "\n").encode("latin-1"))


def estab(cnpj, ordem, inicio, situacao="02", data_sit="", uf="SP", cnae="4781400", **kw):
    return {"cnpj_basico": cnpj, "cnpj_ordem": ordem, "cnpj_dv": "00",
            "matriz_filial": "1" if ordem == "0001" else "2", "nome_fantasia": "Loja Ação",
            "situacao": situacao, "data_situacao": data_sit, "data_inicio": inicio,
            "cnae_principal": cnae, "uf": uf, **kw}


EMPRESAS = [
    # cnpj, natureza, porte
    ("00000001", "2135", "01"),  # MEI ativo
    ("00000002", "2135", "01"),  # MEI baixado em 2024
    ("00000003", "2062", "01"),  # ME com filial
    ("00000004", "2135", "01"),  # era MEI, virou ME, baixada em 2024
    ("00000005", "2062", "05"),  # Demais optante do Simples -> EPP na abertura
    ("00000006", "2054", "05"),  # S.A. fechada, Demais
    ("00000007", "3999", "05"),  # associação: fora do recorte mercantil
    ("00000008", "2062", "01"),  # ME na administração pública (CNAE 84): fora do mercantil
    ("00000009", "2062", "01"),  # no exterior: excluída sempre
    ("00000010", "2062", "03"),  # EPP aberta em 2018
    ("00000011", "2062", "01"),  # data de início inválida: ignorada
]
ESTAB = [
    estab("00000001", "0001", "20230310"),
    estab("00000002", "0001", "20210501", situacao="08", data_sit="20240630"),
    estab("00000003", "0001", "20220115"),
    estab("00000003", "0002", "20230201"),
    estab("00000004", "0001", "20190101", situacao="08", data_sit="20240301"),
    estab("00000005", "0001", "20200701"),
    estab("00000006", "0001", "20210910"),
    estab("00000007", "0001", "20230505", cnae="9430800"),
    estab("00000008", "0001", "20230606", cnae="8411600"),
    estab("00000009", "0001", "20230707", uf="EX"),
    estab("00000010", "0001", "20180808"),
    estab("00000011", "0001", "0"),
]
SIMPLES = [
    {"cnpj_basico": "00000001", "opcao_simples": "N", "opcao_mei": "S",
     "data_opcao_mei": "20230310", "data_exclusao_mei": "00000000"},
    {"cnpj_basico": "00000002", "opcao_simples": "N", "opcao_mei": "N",
     "data_opcao_mei": "20210501", "data_exclusao_mei": "20240630"},
    {"cnpj_basico": "00000004", "opcao_simples": "S", "opcao_mei": "N",
     "data_opcao_simples": "20230101", "data_opcao_mei": "20190101",
     "data_exclusao_mei": "20221231"},
    {"cnpj_basico": "00000005", "opcao_simples": "S", "opcao_mei": "N",
     "data_opcao_simples": "20200701"},
]


@pytest.fixture(scope="module")
def resultado(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("cnpj") / "2026-09"
    pasta.mkdir()
    _zip(pasta, "Estabelecimentos0.zip", "K3241.K03200Y0.D60913.ESTABELE",
         [_linha(e, COLUNAS_ESTAB) for e in ESTAB[:6]])
    _zip(pasta, "Estabelecimentos1.zip", "K3241.K03200Y1.D60913.ESTABELE",
         [_linha(e, COLUNAS_ESTAB) for e in ESTAB[6:]])
    _zip(pasta, "Empresas0.zip", "K3241.K03200Y0.D60913.EMPRECSV",
         [_linha({"cnpj_basico": c, "razao_social": "Empresa São João", "natureza_juridica": n,
                  "capital_social": "1000,00", "porte": p}, COLUNAS_EMPRESAS)
          for c, n, p in EMPRESAS])
    _zip(pasta, "Simples.zip", "F.K03200$W.SIMPLES.CSV.D60913",
         [_linha(s, COLUNAS_SIMPLES) for s in SIMPLES])
    df = processar(pasta, saida=pasta / "saida.csv")
    return df.set_index(["recorte", "ano", "porte"])


def contagem(df, recorte, ano, porte, coluna):
    try:
        return int(df.loc[(recorte, ano, porte), coluna])
    except KeyError:
        return 0


@pytest.mark.parametrize("ano,porte,esperado", [
    (2023, "MEI", 1),     # MEI ativo
    (2021, "MEI", 1),     # MEI depois baixado
    (2019, "MEI", 1),     # era MEI na abertura, hoje é ME
    (2022, "ME", 1),      # matriz da ME
    (2023, "ME", 1),      # filial da ME (a da CNAE 84 fica de fora)
    (2020, "EPP", 1),     # Demais optante do Simples vira EPP
    (2018, "EPP", 1),
    (2021, "Demais", 1),  # S.A. fechada
])
def test_aberturas_mercantis(resultado, ano, porte, esperado):
    assert contagem(resultado, "mercantil", ano, porte, "abertas") == esperado


def test_baixas_classificadas_pelo_porte_na_data_da_baixa(resultado):
    assert contagem(resultado, "mercantil", 2024, "MEI", "fechadas") == 1  # MEI na data da baixa
    assert contagem(resultado, "mercantil", 2024, "ME", "fechadas") == 1   # ex-MEI, já ME


def test_recorte_todas_inclui_nao_mercantis_mas_nunca_o_exterior(resultado):
    assert contagem(resultado, "todas", 2023, "Demais", "abertas") == 1  # associação
    assert contagem(resultado, "todas", 2023, "ME", "abertas") == 2      # filial + CNAE 84
    total_todas = int(resultado.loc["todas", "abertas"].sum())
    assert total_todas == 10  # 12 estabelecimentos - exterior - data inválida


def test_saida_tem_mes_de_referencia(resultado):
    assert set(resultado["mes_referencia_base"]) == {"2026-09"}
