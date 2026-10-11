"""Gera o gráfico e a tabela: `python -m empresas_porte`."""

from __future__ import annotations

import argparse
from pathlib import Path

from empresas_porte.dados import PORTES, carregar_dados, carregar_fontes
from empresas_porte.formatacao import formatar_numero
from empresas_porte.grafico import gerar_grafico


def gerar_tabela_markdown(destino: Path) -> Path:
    """Tabela em Markdown com os números completos, para leitura sem o gráfico."""
    dados = carregar_dados()
    fontes = carregar_fontes()
    linhas = [
        "| Ano | Porte | Abertas | Fechadas | Saldo |",
        "|---:|:---|---:|---:|---:|",
    ]
    for _, r in dados.sort_values(["ano", "porte"]).iterrows():
        abertas = formatar_numero(r["abertas"]) + (" (aprox.)" if r["abertas_aproximado"] else "")
        fechadas = "não divulgado" if r["fechadas"] is None or str(r["fechadas"]) == "<NA>" \
            else formatar_numero(int(r["fechadas"]))
        saldo = "—" if str(r["saldo"]) == "<NA>" else formatar_numero(int(r["saldo"]))
        linhas.append(f"| {r['ano']} | {r['porte']} | {abertas} | {fechadas} | {saldo} |")

    linhas += ["", "Fontes:", ""]
    for id_fonte, f in fontes.iterrows():
        linhas.append(f"- `{id_fonte}`: [{f['titulo']}]({f['url']}), {f['publicador']}, "
                      f"{f['data_publicacao']}. {f['localizacao']}.")

    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / "tabela.md"
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=Path("saida"),
                        help="pasta onde salvar os arquivos (padrão: saida/)")
    args = parser.parse_args()

    dados = carregar_dados()
    assert set(dados["porte"].unique()) == set(PORTES)
    arquivos = gerar_grafico(dados, args.saida)
    arquivos.append(gerar_tabela_markdown(args.saida))
    for a in arquivos:
        print(f"gerado: {a}")


if __name__ == "__main__":
    main()
