"""Relatório em HTML único, com os dois gráficos interativos, tabelas e fontes."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from empresas_porte.dados import NOMES_PORTE, PORTES
from empresas_porte.formatacao import abreviar, formatar_numero
from empresas_porte.grafico import AMARELO, AZUL, EVENTOS, VERDE, VERDE_CLARO

# Chart.js 4.4.1 (licença MIT) vai embutido no HTML: o relatório abre sem internet.
CHARTJS = Path(__file__).resolve().parent / "vendor" / "chart.umd.js"


def _int_ou_none(valor) -> int | None:
    return None if pd.isna(valor) else int(valor)


def _serie_todas(todas: pd.DataFrame) -> dict:
    return {
        "anos": todas["ano"].astype(int).tolist(),
        "abertas": [int(v) for v in todas["abertas"]],
        "fechadas": [int(v) for v in todas["fechadas"]],
        "saldo": [int(v) for v in todas["saldo"]],
        "aprox_abertas": todas["abertas_aproximado"].tolist(),
        "aprox_fechadas": todas["fechadas_aproximado"].tolist(),
    }


def _series_porte(dados: pd.DataFrame) -> dict:
    saida = {}
    for porte in PORTES:
        d = dados[dados["porte"] == porte].sort_values("ano")
        saida[porte] = {
            "nome": NOMES_PORTE[porte],
            "anos": d["ano"].astype(int).tolist(),
            "abertas": [_int_ou_none(v) for v in d["abertas"]],
            "fechadas": [_int_ou_none(v) for v in d["fechadas"]],
            "saldo": [_int_ou_none(v) for v in d["saldo"]],
            "aprox": d["abertas_aproximado"].tolist(),
        }
    return saida


def _tabela_todas(todas: pd.DataFrame) -> str:
    linhas = []
    for _, r in todas.iterrows():
        aprox = r["abertas_aproximado"] or r["fechadas_aproximado"]
        marca = ' <span class="aprox">aprox.</span>' if aprox else ""
        linhas.append(
            f"<tr><td>{r['ano']}{marca}</td><td>{formatar_numero(r['abertas'])}</td>"
            f"<td>{formatar_numero(r['fechadas'])}</td><td>{formatar_numero(r['saldo'])}</td>"
            f"<td><code>{html.escape(str(r['fonte']))}</code></td></tr>"
        )
    return "\n".join(linhas)


def _tabela_porte(dados: pd.DataFrame) -> str:
    linhas = []
    for _, r in dados.sort_values(["ano", "porte"]).iterrows():
        abertas = formatar_numero(r["abertas"])
        if r["abertas_aproximado"]:
            abertas += ' <span class="aprox">aprox.</span>'
        fechadas = "não divulgado" if pd.isna(r["fechadas"]) else formatar_numero(int(r["fechadas"]))
        saldo = "—" if pd.isna(r["saldo"]) else formatar_numero(int(r["saldo"]))
        linhas.append(
            f"<tr><td>{r['ano']}</td><td>{r['porte']}</td><td>{abertas}</td>"
            f"<td>{fechadas}</td><td>{saldo}</td></tr>"
        )
    return "\n".join(linhas)


def _lista_fontes(fontes: pd.DataFrame) -> str:
    itens = []
    for id_fonte, f in fontes.iterrows():
        itens.append(
            f'<li><code>{html.escape(id_fonte)}</code> · '
            f'<a href="{html.escape(f["url"])}" target="_blank" rel="noopener">'
            f'{html.escape(f["titulo"])}</a>, {html.escape(str(f["publicador"]))}, '
            f'{html.escape(str(f["data_publicacao"]))}. '
            f'<span class="muted">{html.escape(str(f["localizacao"]))}</span></li>'
        )
    return "\n".join(itens)


def gerar_relatorio_html(
    dados: pd.DataFrame, todas: pd.DataFrame, fontes: pd.DataFrame, destino: Path
) -> Path:
    ultimo = todas.iloc[-1]
    primeiro_exato = todas[~todas["fechadas_aproximado"]].iloc[0]
    mei_2024 = dados[(dados["ano"] == 2024) & (dados["porte"] == "MEI")].iloc[0]
    pn_2024 = dados[dados["ano"] == 2024]
    participacao_mei = int(mei_2024["fechadas"]) / int(pn_2024["fechadas"].sum())

    payload = {
        "todas": _serie_todas(todas),
        "porte": _series_porte(dados),
        "eventos": {str(k): v.replace("\n", " ") for k, v in EVENTOS.items()},
        "cores": {"verde": VERDE, "verdeClaro": VERDE_CLARO, "amarelo": AMARELO, "azul": AZUL},
    }

    pagina = MODELO
    substituicoes = {
        "{{DADOS_JSON}}": json.dumps(payload, ensure_ascii=False),
        "{{ANO_FIM}}": str(int(ultimo["ano"])),
        "{{ANO_INI}}": str(int(todas["ano"].min())),
        "{{KPI_ABERTAS}}": abreviar(ultimo["abertas"]),
        "{{KPI_FECHADAS}}": abreviar(ultimo["fechadas"]),
        "{{KPI_SALDO}}": abreviar(ultimo["saldo"]),
        "{{KPI_FECH_ANO_BASE}}": str(int(primeiro_exato["ano"])),
        "{{KPI_FECH_MULT}}": formatar_numero(ultimo["fechadas"] / primeiro_exato["fechadas"], 1),
        "{{KPI_MEI_PCT}}": formatar_numero(participacao_mei * 100, 0),
        "{{TABELA_TODAS}}": _tabela_todas(todas),
        "{{TABELA_PORTE}}": _tabela_porte(dados),
        "{{FONTES}}": _lista_fontes(fontes),
    }
    # Chart.js por último, para que marcadores dentro da biblioteca não sejam tocados.
    pagina = pagina.replace("{{CHARTJS}}", "{{__CHARTJS__}}")
    for chave, valor in substituicoes.items():
        pagina = pagina.replace(chave, valor)

    biblioteca = CHARTJS.read_text(encoding="utf-8").replace("</script", "<\\/script")
    pagina = pagina.replace("{{__CHARTJS__}}", biblioteca)

    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / "relatorio.html"
    caminho.write_text(pagina, encoding="utf-8")
    return caminho


MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Empresas abertas e fechadas no Brasil</title>
<style>
:root{
  --fundo:#FCFCFB; --cartao:#F4F3EF; --tinta:#1B1B1B; --tinta2:#55534E; --suave:#7A7872;
  --borda:rgba(11,11,11,.10); --grade:#E1E0D9; --verde:#00873A; --amarelo:#E5A800; --azul:#1F4FA3;
  --faixa:linear-gradient(90deg,#00873A 0 60%,#E5A800 60% 80%,#1F4FA3 80% 100%);
}
@media (prefers-color-scheme: dark){:root{
  --fundo:#161615; --cartao:#21211F; --tinta:#F0EFEC; --tinta2:#C3C2B7; --suave:#9A988F;
  --borda:rgba(255,255,255,.10); --grade:#2C2C2A;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--fundo);color:var(--tinta);
  font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.faixa{height:6px;background:var(--faixa)}
main{max-width:1080px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:30px;line-height:1.2;margin:0 0 8px;font-weight:700;letter-spacing:-.01em}
h2{font-size:21px;margin:48px 0 4px;font-weight:700}
.sub{color:var(--tinta2);margin:0 0 4px}
.muted{color:var(--suave)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:28px 0 8px}
.kpi{background:var(--cartao);border-radius:10px;padding:16px 18px}
.kpi .rot{font-size:13px;color:var(--tinta2)}
.kpi .val{font-size:30px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.2;margin-top:4px}
.kpi .det{font-size:13px;color:var(--suave)}
.legenda{display:flex;flex-wrap:wrap;gap:18px;font-size:13px;color:var(--tinta2);margin:14px 0 6px}
.legenda span{display:inline-flex;align-items:center;gap:6px}
.q{width:11px;height:11px;border-radius:2px;display:inline-block}
.linha{width:18px;height:0;border-top:2px dashed var(--azul);display:inline-block}
.grafico{position:relative;height:380px}
.grafico.peq{height:250px}
.grade-porte{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:28px 32px;margin-top:8px}
.grade-porte .mei{grid-column:1/-1}
h3{font-size:15px;margin:0 0 4px;font-weight:600}
.nota{font-size:13px;color:var(--suave);margin:10px 0 0}
.eventos{font-size:14px;color:var(--tinta2);margin:12px 0 0;padding-left:18px}
details{margin-top:16px;border:1px solid var(--borda);border-radius:10px;padding:10px 16px}
summary{cursor:pointer;font-weight:600}
.tabela{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums;margin:12px 0}
th,td{padding:7px 10px;border-bottom:1px solid var(--borda);text-align:right;white-space:nowrap}
th:first-child,td:first-child,table.porte th:nth-child(2),table.porte td:nth-child(2){text-align:left}
th{color:var(--tinta2);font-weight:600}
.aprox{font-size:11px;color:var(--suave);border:1px solid var(--borda);border-radius:4px;padding:0 4px}
ul.fontes{padding-left:18px;font-size:14px}
ul.fontes li{margin:6px 0}
a{color:var(--azul)}
@media (prefers-color-scheme: dark){a{color:#7FA6E8}.linha{border-top-color:#6E9BE8}}
footer{margin-top:48px;font-size:13px;color:var(--suave);border-top:1px solid var(--borda);padding-top:16px}
@media (max-width:600px){h1{font-size:24px}.grafico{height:300px}}
</style>
</head>
<body>
<div class="faixa" aria-hidden="true"></div>
<main>
<h1>Empresas abertas e fechadas no Brasil</h1>
<p class="sub">Todas as empresas de {{ANO_INI}} a {{ANO_FIM}} e o detalhe por porte (MEI, ME e EPP) de 2019 a 2025.</p>

<section class="kpis" aria-label="Resumo de {{ANO_FIM}}">
  <div class="kpi"><div class="rot">Empresas abertas em {{ANO_FIM}}</div><div class="val">{{KPI_ABERTAS}}</div><div class="det">todas as classes</div></div>
  <div class="kpi"><div class="rot">Empresas fechadas em {{ANO_FIM}}</div><div class="val">{{KPI_FECHADAS}}</div><div class="det">{{KPI_FECH_MULT}}× o número de {{KPI_FECH_ANO_BASE}}</div></div>
  <div class="kpi"><div class="rot">Saldo em {{ANO_FIM}}</div><div class="val">{{KPI_SALDO}}</div><div class="det">abertas menos fechadas</div></div>
  <div class="kpi"><div class="rot">MEI nos fechamentos de pequenos negócios</div><div class="val">{{KPI_MEI_PCT}}%</div><div class="det">em 2024, segundo o Sebrae</div></div>
</section>

<h2>Todas as empresas, {{ANO_INI}} a {{ANO_FIM}}</h2>
<p class="sub">Todas as classes (MEI, ME, EPP, médias e grandes), matrizes e filiais. Fonte: Mapa de Empresas, Governo Federal.</p>
<div class="legenda">
  <span><i class="q" style="background:var(--verde)"></i>Abertas</span>
  <span><i class="q" style="background:var(--amarelo)"></i>Fechadas</span>
  <span><i class="linha"></i>Saldo (abertas − fechadas)</span>
</div>
<div class="grafico"><canvas id="g-todas" role="img" aria-label="Empresas abertas, fechadas e saldo no Brasil de {{ANO_INI}} a {{ANO_FIM}}"></canvas></div>
<ul class="eventos" id="eventos"></ul>
<p class="nota">De 2010 a 2019 os valores vêm do histórico publicado no boletim de 2020, arredondado em dezenas de milhar. Passe o mouse sobre as barras para ver os números.</p>

<h2>Por porte, 2019 a 2025</h2>
<p class="sub">Pequenos negócios por porte. Fonte: Sebrae, com base no cadastro de CNPJ da Receita Federal.</p>
<div class="legenda">
  <span><i class="q" style="background:var(--verde)"></i>Abertas</span>
  <span><i class="q" style="background:#8CCBA4;outline:1px solid var(--verde)"></i>Abertas em 2025 (relatório anual de 2025)</span>
  <span><i class="q" style="background:var(--amarelo)"></i>Fechadas</span>
  <span><i class="linha"></i>Saldo</span>
</div>
<div class="grade-porte">
  <div class="mei"><h3 id="t-MEI"></h3><div class="grafico peq"><canvas id="g-MEI" role="img" aria-label="MEI: abertas, fechadas e saldo"></canvas></div></div>
  <div><h3 id="t-ME"></h3><div class="grafico peq"><canvas id="g-ME" role="img" aria-label="Microempresas: abertas, fechadas e saldo"></canvas></div></div>
  <div><h3 id="t-EPP"></h3><div class="grafico peq"><canvas id="g-EPP" role="img" aria-label="Empresas de pequeno porte: abertas, fechadas e saldo"></canvas></div></div>
</div>
<p class="nota">Os fechamentos de 2025 por porte ainda não foram divulgados. O número de MEI abertos em 2025 é aproximado (3,81 mi). As médias e grandes empresas não têm painel próprio porque nenhuma fonte aberta publica as aberturas e os fechamentos dessa classe ano a ano.</p>

<h2>Tabelas</h2>
<details open>
<summary>Todas as empresas (Mapa de Empresas)</summary>
<div class="tabela"><table>
<thead><tr><th>Ano</th><th>Abertas</th><th>Fechadas</th><th>Saldo</th><th>Fonte</th></tr></thead>
<tbody>
{{TABELA_TODAS}}
</tbody></table></div>
</details>
<details>
<summary>Por porte (Sebrae)</summary>
<div class="tabela"><table class="porte">
<thead><tr><th>Ano</th><th>Porte</th><th>Abertas</th><th>Fechadas</th><th>Saldo</th></tr></thead>
<tbody>
{{TABELA_PORTE}}
</tbody></table></div>
</details>

<h2>Fontes</h2>
<ul class="fontes">
{{FONTES}}
</ul>

<h2>Como ler estes números</h2>
<ul class="fontes">
<li><strong>Abertura</strong> é a inscrição de um CNPJ no ano; <strong>fechamento</strong> é a baixa do CNPJ. Os dois incluem matrizes e filiais.</li>
<li><strong>Saldo</strong> é abertas menos fechadas no ano. Não é o estoque de empresas ativas.</li>
<li>Parte dos fechamentos vem de ações do governo, como cancelamentos em massa de MEI inadimplentes, e não só de empresas que pararam de funcionar.</li>
<li>Os dois gráficos usam fontes com metodologias diferentes. Não some nem subtraia os números de um com os do outro.</li>
<li>Antes de 2009 não existia MEI, por isso o detalhe por porte começa em 2019 e a série longa mostra só o total.</li>
</ul>

<footer>Gerado pelo projeto <code>empresas-brasil-porte</code> com <code>python -m empresas_porte</code>. Código sob licença MIT; dados do Sebrae e do Mapa de Empresas.</footer>
</main>

<script>{{CHARTJS}}</script>
<script>
const D = {{DADOS_JSON}};
const fmt = new Intl.NumberFormat('pt-BR');
function curto(v){
  if (v === null || v === undefined) return '—';
  const a = Math.abs(v), s = v < 0 ? '-' : '';
  if (a >= 1e6) { const m = a/1e6; return s + m.toLocaleString('pt-BR',{maximumFractionDigits: m % 1 === 0 ? 0 : 1}) + ' mi'; }
  if (a >= 1e3) return s + Math.round(a/1e3).toLocaleString('pt-BR') + ' mil';
  return s + fmt.format(a);
}
const escuro = matchMedia('(prefers-color-scheme: dark)').matches;
const GRADE = escuro ? '#2C2C2A' : '#E1E0D9', TICK = escuro ? '#9A988F' : '#7A7872';
const C = Object.assign({}, D.cores, escuro ? {azul:'#6E9BE8'} : {});

function opcoes(extraTooltip, pularRotulos){
  return {
    responsive:true, maintainAspectRatio:false,
    interaction:{mode:'index', intersect:false},
    plugins:{legend:{display:false}, tooltip:{callbacks:{
      title: it => 'Ano ' + it[0].label,
      label: c => {
        if (c.raw === null) return ' ' + c.dataset.label + ': não divulgado';
        return ' ' + c.dataset.label + ': ' + fmt.format(c.raw) + (extraTooltip ? extraTooltip(c) : '');
      }
    }}},
    scales:{
      x:{grid:{display:false}, ticks:{color:TICK, autoSkip:!!pularRotulos, maxRotation:0}},
      y:{beginAtZero:true, grid:{color:GRADE}, border:{display:false}, ticks:{color:TICK, callback:curto}}
    }
  };
}
function conjuntos(abertas, fechadas, saldo, coresAbertas){
  return [
    {type:'bar', label:'Abertas', data:abertas, backgroundColor:coresAbertas, borderRadius:3, maxBarThickness:26, order:2},
    {type:'bar', label:'Fechadas', data:fechadas, backgroundColor:C.amarelo, borderRadius:3, maxBarThickness:26, order:2},
    {type:'line', label:'Saldo', data:saldo, borderColor:C.azul, backgroundColor:C.azul, borderWidth:2,
     borderDash:[5,4], pointRadius:3.5, pointHoverRadius:5, pointBorderColor:escuro?'#161615':'#FCFCFB', pointBorderWidth:1.5,
     tension:.15, spanGaps:false, order:1}
  ];
}

// Todas as empresas
const T = D.todas;
new Chart(document.getElementById('g-todas'), {
  data:{labels:T.anos, datasets:conjuntos(T.abertas, T.fechadas, T.saldo, C.verde)},
  options:opcoes(c => {
    const i = c.dataIndex;
    const aprox = (c.datasetIndex === 0 && T.aprox_abertas[i]) || (c.datasetIndex === 1 && T.aprox_fechadas[i])
               || (c.datasetIndex === 2 && (T.aprox_abertas[i] || T.aprox_fechadas[i]));
    return aprox ? ' (aprox.)' : '';
  }, true)
});
const ul = document.getElementById('eventos');
Object.entries(D.eventos).forEach(([ano, txt]) => {
  const li = document.createElement('li');
  li.innerHTML = '<strong>' + ano + ':</strong> pico de fechamentos. ' + txt + '.';
  ul.appendChild(li);
});

// Por porte
Object.entries(D.porte).forEach(([porte, s]) => {
  document.getElementById('t-' + porte).textContent = s.nome;
  const cores = s.fechadas.map(f => f === null ? C.verdeClaro : C.verde);
  new Chart(document.getElementById('g-' + porte), {
    data:{labels:s.anos, datasets:conjuntos(s.abertas, s.fechadas, s.saldo, cores)},
    options:opcoes(c => (c.datasetIndex === 0 && s.aprox[c.dataIndex]) ? ' (aprox.)' : '')
  });
});
</script>
</body>
</html>
"""
