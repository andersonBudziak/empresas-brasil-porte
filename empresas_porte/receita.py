"""Aberturas e baixas por ano e porte a partir da base aberta de CNPJ da Receita Federal.

A base é publicada todo mês em
https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/AAAA-MM/
(também listada no Portal Brasileiro de Dados Abertos, dados.gov.br). Ela tem dezenas
de GB descompactada, por isso este módulo roda na sua máquina, não no CI.

Uso:

    # 1. baixar os arquivos de um mês (ou baixe manualmente para a mesma pasta)
    python -m empresas_porte.receita baixar 2026-09 --pasta ~/cnpj/2026-09

    # 2. processar e gravar dados/receita_cnpj_por_porte.csv
    python -m empresas_porte.receita processar --pasta ~/cnpj/2026-09

A metodologia replica a do estudo do Sebrae usado no projeto (2019–2024):

- **Abertura**: estabelecimento (matriz ou filial) com DATA DE INÍCIO ATIVIDADE no ano.
- **Baixa**: estabelecimento com SITUAÇÃO CADASTRAL 08 (baixada) e DATA SITUAÇÃO
  CADASTRAL no ano.
- **MEI**: optante pelo MEI na data da abertura (aberturas) ou na data da baixa (baixas),
  segundo as datas de opção e exclusão do arquivo Simples.
- **ME / EPP**: porte da empresa no arquivo Empresas (01 = ME, 03 = EPP). Empresas de
  porte 05 ("Demais") optantes do Simples Nacional na data de abertura viram EPP.
- **Demais**: o restante (médias e grandes, e não informado).
- **Recorte "mercantil"** (como o Sebrae): só as naturezas jurídicas empresariais do
  Quadro 1 do estudo e sem as divisões CNAE 84, 94 e 99. O arquivo de saída traz também
  o recorte "todas", sem esse filtro, para comparar com o Mapa de Empresas.

Limitações: o porte ME/EPP é o atual, não o da época; a base é uma foto do cadastro no
mês de referência, e baixas de anos passados podem ser registradas com atraso.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
import zipfile
from pathlib import Path

URL_BASE = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj"
ARQUIVOS = (
    [f"Estabelecimentos{i}.zip" for i in range(10)]
    + [f"Empresas{i}.zip" for i in range(10)]
    + ["Simples.zip"]
)
SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "receita_cnpj_por_porte.csv"

# Naturezas jurídicas do Quadro 1 do estudo do Sebrae (código sem hífen, como na base).
NATUREZAS_MERCANTIS = (
    2046, 2054, 2062, 2097, 2127, 2135, 2143, 2151, 2160, 2224, 2232, 2240, 2259,
    2267, 2283, 2291, 2305, 2313, 2321, 2330, 2348, 4014, 4022, 4081, 4111, 4120,
)
DIVISOES_CNAE_EXCLUIDAS = (84, 94, 99)

COLUNAS_ESTAB = [
    "cnpj_basico", "cnpj_ordem", "cnpj_dv", "matriz_filial", "nome_fantasia",
    "situacao", "data_situacao", "motivo_situacao", "cidade_exterior", "pais",
    "data_inicio", "cnae_principal", "cnae_secundaria", "tipo_logradouro", "logradouro",
    "numero", "complemento", "bairro", "cep", "uf", "municipio", "ddd1", "telefone1",
    "ddd2", "telefone2", "ddd_fax", "fax", "email", "situacao_especial",
    "data_situacao_especial",
]
COLUNAS_EMPRESAS = [
    "cnpj_basico", "razao_social", "natureza_juridica", "qualificacao_responsavel",
    "capital_social", "porte", "ente_federativo",
]
COLUNAS_SIMPLES = [
    "cnpj_basico", "opcao_simples", "data_opcao_simples", "data_exclusao_simples",
    "opcao_mei", "data_opcao_mei", "data_exclusao_mei",
]


# ------------------------------------------------------------------ download
def baixar(mes: str, pasta: Path, url_base: str = URL_BASE) -> list[Path]:
    """Baixa os zips de Estabelecimentos, Empresas e Simples do mês AAAA-MM."""
    pasta.mkdir(parents=True, exist_ok=True)
    baixados = []
    for nome in ARQUIVOS:
        destino = pasta / nome
        if destino.exists() and destino.stat().st_size > 0:
            print(f"já existe: {destino.name}")
            baixados.append(destino)
            continue
        url = f"{url_base}/{mes}/{nome}"
        print(f"baixando {url}")
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(destino, "wb") as f:
                while bloco := resp.read(1 << 20):
                    f.write(bloco)
        except Exception as erro:  # noqa: BLE001
            destino.unlink(missing_ok=True)
            sys.exit(
                f"Falha ao baixar {url}: {erro}\n"
                "Se a Receita mudou o endereço, baixe os arquivos manualmente pelo Portal de "
                "Dados Abertos (dados.gov.br, conjunto 'Cadastro Nacional da Pessoa Jurídica') "
                f"para {pasta} e rode o comando 'processar'."
            )
        baixados.append(destino)
    return baixados


# ------------------------------------------------------------------ extração
def _extrair(pasta: Path) -> dict[str, list[Path]]:
    """Descompacta os zips em pasta/csv/ (uma vez) e agrupa os CSVs por tipo."""
    destino = pasta / "csv"
    destino.mkdir(exist_ok=True)
    grupos: dict[str, list[Path]] = {"estab": [], "empresas": [], "simples": []}
    for zip_path in sorted(pasta.glob("*.zip")):
        nome = zip_path.stem.lower()
        tipo = ("estab" if nome.startswith("estabelecimentos") else
                "empresas" if nome.startswith("empresas") else
                "simples" if nome.startswith("simples") else None)
        if tipo is None:
            continue
        csv_path = destino / f"{zip_path.stem}.csv"
        if not csv_path.exists():
            with zipfile.ZipFile(zip_path) as z:
                membro = z.namelist()[0]
                with z.open(membro) as src, open(csv_path, "wb") as dst:
                    while bloco := src.read(1 << 22):
                        dst.write(bloco)
        grupos[tipo].append(csv_path)
    faltando = [t for t, v in grupos.items() if not v]
    if faltando:
        sys.exit(f"Arquivos não encontrados em {pasta}: {', '.join(faltando)}. "
                 "Esperado: Estabelecimentos*.zip, Empresas*.zip e Simples.zip.")
    return grupos


# ------------------------------------------------------------------ cálculo
def _leitor(arquivos: list[Path], colunas: list[str]) -> str:
    lista = ", ".join(f"'{p.as_posix()}'" for p in arquivos)
    tipos = ", ".join(f"'{c}': 'VARCHAR'" for c in colunas)
    return (f"read_csv([{lista}], delim=';', quote='\"', header=false, encoding='latin-1', "
            f"columns={{{tipos}}}, ignore_errors=true)")


def _data(col: str) -> str:
    """Datas vêm como AAAAMMDD; 0, vazio ou inválido vira NULL."""
    return f"TRY_STRPTIME(NULLIF(NULLIF(TRIM({col}), ''), '0'), '%Y%m%d')::DATE"


def montar_sql(grupos: dict[str, list[Path]]) -> str:
    naturezas = ", ".join(str(n) for n in NATUREZAS_MERCANTIS)
    divisoes = ", ".join(str(d) for d in DIVISOES_CNAE_EXCLUIDAS)
    return f"""
    WITH estab AS (
        SELECT TRY_CAST(cnpj_basico AS INTEGER) AS cnpj_basico,
               TRIM(situacao) AS situacao,
               {_data('data_situacao')} AS data_situacao,
               {_data('data_inicio')} AS data_inicio,
               TRY_CAST(SUBSTR(LPAD(TRIM(cnae_principal), 7, '0'), 1, 2) AS INTEGER) AS divisao,
               TRIM(uf) AS uf
        FROM {_leitor(grupos['estab'], COLUNAS_ESTAB)}
    ),
    empresas AS (
        SELECT TRY_CAST(cnpj_basico AS INTEGER) AS cnpj_basico,
               TRY_CAST(natureza_juridica AS INTEGER) AS natureza,
               LPAD(TRIM(porte), 2, '0') AS porte
        FROM {_leitor(grupos['empresas'], COLUNAS_EMPRESAS)}
    ),
    simples AS (
        SELECT TRY_CAST(cnpj_basico AS INTEGER) AS cnpj_basico,
               {_data('data_opcao_simples')} AS ini_simples,
               {_data('data_exclusao_simples')} AS fim_simples,
               {_data('data_opcao_mei')} AS ini_mei,
               {_data('data_exclusao_mei')} AS fim_mei
        FROM {_leitor(grupos['simples'], COLUNAS_SIMPLES)}
    ),
    base AS (
        SELECT e.*, emp.natureza, emp.porte, s.ini_simples, s.fim_simples, s.ini_mei, s.fim_mei,
               (emp.natureza IN ({naturezas}) AND COALESCE(e.divisao, 0) NOT IN ({divisoes}))
                   AS mercantil
        FROM estab e
        LEFT JOIN empresas emp USING (cnpj_basico)
        LEFT JOIN simples s USING (cnpj_basico)
        WHERE COALESCE(e.uf, '') <> 'EX'
    ),
    eventos AS (
        SELECT 'abertas' AS evento, data_inicio AS data, * FROM base
        WHERE data_inicio IS NOT NULL
        UNION ALL
        SELECT 'fechadas' AS evento, data_situacao AS data, * FROM base
        WHERE situacao IN ('8', '08') AND data_situacao IS NOT NULL
    ),
    classificados AS (
        SELECT evento, YEAR(data) AS ano, mercantil,
            CASE
                WHEN ini_mei IS NOT NULL AND ini_mei <= data
                     AND (fim_mei IS NULL OR fim_mei >= data) THEN 'MEI'
                WHEN porte = '01' THEN 'ME'
                WHEN porte = '03' THEN 'EPP'
                WHEN porte = '05' AND evento = 'abertas' AND ini_simples IS NOT NULL
                     AND ini_simples <= data AND (fim_simples IS NULL OR fim_simples >= data)
                     THEN 'EPP'
                ELSE 'Demais'
            END AS porte
        FROM eventos
    )
    SELECT ano, recorte, porte,
           SUM(CASE WHEN evento = 'abertas' THEN 1 ELSE 0 END) AS abertas,
           SUM(CASE WHEN evento = 'fechadas' THEN 1 ELSE 0 END) AS fechadas
    FROM (
        SELECT evento, ano, porte, 'mercantil' AS recorte FROM classificados WHERE mercantil
        UNION ALL
        SELECT evento, ano, porte, 'todas' AS recorte FROM classificados
    )
    GROUP BY ano, recorte, porte
    ORDER BY recorte, ano, porte
    """


def processar(pasta: Path, saida: Path = SAIDA_PADRAO, mes_referencia: str | None = None,
              ano_inicial: int = 2000):
    """Calcula aberturas e baixas por ano, recorte e porte e grava o CSV."""
    import duckdb

    grupos = _extrair(pasta)
    con = duckdb.connect()
    # A junção de ~60 milhões de estabelecimentos pode passar da memória: deixe o DuckDB
    # usar o disco ao lado dos arquivos.
    (pasta / "tmp_duckdb").mkdir(exist_ok=True)
    con.execute(f"SET temp_directory = '{(pasta / 'tmp_duckdb').as_posix()}'")
    con.execute("SET preserve_insertion_order = false")
    df = con.execute(montar_sql(grupos)).df()
    df = df[df["ano"] >= ano_inicial].copy()
    df["abertas"] = df["abertas"].astype(int)
    df["fechadas"] = df["fechadas"].astype(int)
    df["mes_referencia_base"] = mes_referencia or pasta.name
    saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(saida, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Base aberta de CNPJ da Receita Federal")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_baixar = sub.add_parser("baixar", help="baixa os zips de um mês")
    p_baixar.add_argument("mes", help="mês de referência, AAAA-MM")
    p_baixar.add_argument("--pasta", type=Path, required=True)
    p_baixar.add_argument("--url-base", default=URL_BASE)
    p_proc = sub.add_parser("processar", help="calcula aberturas e baixas por ano e porte")
    p_proc.add_argument("--pasta", type=Path, required=True)
    p_proc.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    p_proc.add_argument("--mes", help="mês de referência da base (padrão: nome da pasta)")
    p_proc.add_argument("--ano-inicial", type=int, default=2000)
    args = parser.parse_args()

    if args.comando == "baixar":
        baixar(args.mes, args.pasta, args.url_base)
    else:
        df = processar(args.pasta, args.saida, args.mes, args.ano_inicial)
        print(f"gravado: {args.saida} ({len(df)} linhas)")
        print(df[df["recorte"] == "mercantil"].pivot_table(
            index="ano", columns="porte", values="fechadas", aggfunc="sum").tail(8))


if __name__ == "__main__":
    main()
