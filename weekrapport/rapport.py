"""Het rapport schrijven: Markdown (om te plakken), HTML (om te lezen/mailen) en schone data (CSV)."""
from __future__ import annotations

import csv
import html
import re
from datetime import datetime
from pathlib import Path

from .analyse import Analyse
from .config import KlantConfig
from .opmaak import eur, getal, pct, pct_verschil, verandering, weekperiode, datum, week_kort, MIN
from .opschonen import Dataset


# ---------------------------------------------------------------- markdown

def _kpi_tabel(a: Analyse) -> list[str]:
    t, v, g = a.totaal, a.totaal_vorig, a.gemiddelde_eerder
    rijen = [
        ("Uitgaven", lambda c: c.spend, eur),
        ("Impressies", lambda c: c.impressies, getal),
        ("Klikken", lambda c: c.klikken, getal),
        ("CTR", lambda c: c.ctr, pct),
        ("Kosten per klik", lambda c: c.cpc, eur),
        ("Leads", lambda c: c.leads, getal),
        ("Kosten per lead", lambda c: c.kosten_per("leads"), eur),
    ]
    if a.heeft_conversies:
        rijen += [("Websiteconversies", lambda c: c.conversies, getal),
                  ("Kosten per conversie", lambda c: c.kosten_per("conversies"), eur)]
    kop = "| | Deze week |"
    lijn = "|---|---:|"
    if v:
        kop += " Vorige week | Verschil |"
        lijn += "---:|---:|"
    if g and len(a.weken) > 2:
        kop += f" Gem. {len(a.weken) - 1} weken ervoor |"
        lijn += "---:|"
    regels = [kop, lijn]
    for naam, f, fmt in rijen:
        r = f"| {naam} | {fmt(f(t))} |"
        if v:
            r += f" {fmt(f(v))} | {pct_verschil(verandering(f(t), f(v)))} |"
        if g and len(a.weken) > 2:
            r += f" {fmt(f(g))} |"
        regels.append(r)
    return regels


def _segment_tabel(a: Analyse, dim: str) -> list[str]:
    kpi, T = a.kpi, a.t["Kosten"]
    conv = a.heeft_conversies and kpi == "leads"
    n = len(a.weken)
    kop = f"| Segment | Uitgaven | Budgetaandeel | CTR | Leads | {T} |"
    lijn = "|---|---:|---:|---:|---:|---:|"
    if conv:
        kop += " Conversies |"
        lijn += "---:|"
    if n > 1:
        kop += f" {T}, {n} wk |" + (f" Conversies, {n} wk |" if conv else "")
        lijn += "---:|" + ("---:|" if conv else "")
    regels = [kop, lijn]
    markering = {"uitsluiten": " ⚠", "afschalen": " ⚠", "kwaliteit": " ?", "opschalen": " ★"}
    for s in sorted(a.segmenten[dim], key=lambda s: -s.nu.spend):
        nu, vo = s.nu, s.vorig
        def overgang(f, fmt):
            if vo is None or f(vo) is None:
                return fmt(f(nu))
            return f"{fmt(f(vo))} → {fmt(f(nu))}"
        aandeel = (f"{pct(s.aandeel_vorig, 0)} → {pct(s.aandeel_nu, 0)}" if s.aandeel_vorig is not None
                   else pct(s.aandeel_nu, 0))
        r = (f"| {s.waarde}{markering.get(s.categorie, '')} | {eur(nu.spend)} | {aandeel} | {pct(nu.ctr)} | "
             f"{getal(nu.leads)} | {overgang(lambda c: c.kosten_per(kpi), eur)} |")
        if conv:
            r += f" {getal(nu.conversies)} |"
        if n > 1:
            r += f" {eur(s.periode.kosten_per(kpi))} |" + (f" {getal(s.periode.conversies)} |" if conv else "")
        regels.append(r)
    return regels


def maak_markdown(a: Analyse, data: Dataset, cfg: KlantConfig, gemaakt: datetime) -> str:
    md: list[str] = []
    bron_deze_week = data.weekbron[a.week]
    md += [f"# Weekrapportage {a.klant}", "",
           f"**Week van {weekperiode(a.week)}**" + (f" · vergeleken met {weekperiode(a.vorige)}" if a.vorige else ""), "",
           f"Gemaakt op {datum(gemaakt.date())} om {gemaakt:%H:%M} uit {bron_deze_week}"
           + (f" en {len(data.exports) - 1} eerdere export(s)" if len(data.exports) > 1 else "")
           + f". Historie: {len(a.weken)} weken ({week_kort(a.weken[0])} t/m {week_kort(a.week)}).", ""]

    md += ["## In het kort", ""] + [f"- {k}" for k in a.kort] + [""]

    md += ["## Wat veranderde", ""] + _kpi_tabel(a) + [""]
    md += [f"- {v}" for v in a.veranderingen] + ([""] if a.veranderingen else [])

    md += ["## Wat aandacht vraagt", ""]
    if a.aandacht:
        md += [f"- **{p.onderwerp}**: {p.tekst}" for p in a.aandacht] + [""]
    else:
        md += ["Niets dat de drempels overschrijdt.", ""]
    if a.kansen:
        md += ["**Wat goed werkt**", ""] + [f"- **{p.onderwerp}**: {p.tekst}" for p in a.kansen] + [""]

    md += ["## Wat ik zou doen", ""] + [f"{i}. {x}" for i, x in enumerate(a.acties, 1)] + [""]

    md += ["## Details per segment", "",
           "⚠ = te duur of geen resultaat · ? = check leadkwaliteit · ★ = kans om op te schalen. "
           "Pijltjes tonen vorige week → deze week.", ""]
    for d in a.dimensies:
        nieuw = " (nieuw deze week)" if d in a.nieuwe_dimensies else ""
        md += [f"### {d}{nieuw}", ""] + _segment_tabel(a, d) + [""]

    md += _datakwaliteit(a, data)

    dr = cfg.drempels
    md += ["## Over dit rapport", "",
           "- Functie, Bedrijfsgrootte enz. zijn verschillende opdelingen van dezelfde campagnes. Binnen één dimensie tellen de "
           "segmenten op tot het totaal. Tel ze nooit op over dimensies heen, want dan tel je alles dubbel.",
           "- De aantallen per segment zijn klein (vaak minder dan 10 leads per week). De signalen gelden daarom pas vanaf "
           f"{eur(dr['min_uitgaven_week'], None)} uitgaven per week of {eur(dr['min_uitgaven_periode'], None)} over de hele periode, "
           f"en waar het kan wordt over alle {len(a.weken)} weken gekeken. Zie ze als richting, niet als bewijs.",
           f"- 'Gemiddeld' is het totaal van het account. Een segment is 'te duur' vanaf {str(dr['factor_duur']).replace('.', ',')}× en "
           f"'een kans' bij {str(dr['factor_goedkoop']).replace('.', ',')}× of minder van de gemiddelde {a.t['kosten']}. "
           f"De drempels staan in `klanten/{cfg.sleutel}.toml`.",
           "- CTR, kosten per klik en kosten per lead rekent het script zelf uit klikken, impressies en uitgaven. "
           "De CTR uit de export wordt alleen gebruikt als controle.", ""]
    return "\n".join(md)


def _datakwaliteit(a: Analyse, data: Dataset) -> list[str]:
    relevant = [m for m in data.meldingen if m.week is None or m.week <= a.week]
    groepen = [("controleren", "Controleren", "Dit kon het script niet zelf oplossen. Kijk ernaar voordat je het rapport deelt."),
               ("gecorrigeerd", "Automatisch gecorrigeerd", None),
               ("info", "Opbouw van de exports", None)]
    md = ["## Datakwaliteit", ""]
    if not relevant:
        return md + ["Geen bijzonderheden: de exports waren compleet en consistent.", ""]
    md += ["Het script controleert elke export en lost wat kan zelf op. Er wordt niets stil aangepast: alles staat hieronder. "
           "Elke dimensie hoort op hetzelfde totaal uit te komen; als dat niet zo is, staat het onder *Controleren*.", ""]
    for niveau, titel, uitleg in groepen:
        ms = [m for m in relevant if m.niveau == niveau]
        if not ms:
            continue
        ms.sort(key=lambda m: (m.week is None, -(m.week.toordinal() if m.week else 0)))
        md += [f"**{titel}**", ""] + ([uitleg, ""] if uitleg else [])
        md += [f"- {m.tekst}" for m in ms] + [""]
    if not any(m.niveau == "controleren" for m in relevant):
        md += ["Niets om handmatig te controleren: de totalen per dimensie kloppen in alle weken.", ""]
    return md


# ---------------------------------------------------------------- html

CSS = """
:root{--bg:#f7f7f5;--card:#ffffff;--tekst:#1d1d1b;--zacht:#5f5f5a;--lijn:#e2e1dc;--accent:#0b5cad;--kop:#f0efea}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#161615;--card:#1f1f1d;--tekst:#ecebe6;--zacht:#a3a29b;--lijn:#3a3936;--accent:#7ab4ff;--kop:#2a2927}}
:root[data-theme="dark"]{--bg:#161615;--card:#1f1f1d;--tekst:#ecebe6;--zacht:#a3a29b;--lijn:#3a3936;--accent:#7ab4ff;--kop:#2a2927}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tekst);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;margin:0 0 8px;letter-spacing:-.01em}
h2{font-size:20px;margin:40px 0 12px;padding-top:16px;border-top:1px solid var(--lijn)}
h3{font-size:16px;margin:24px 0 8px}
p{margin:8px 0}
ul,ol{padding-left:22px;margin:8px 0}
li{margin:6px 0}
strong{font-weight:600}
code{font:13px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--kop);padding:1px 5px;border-radius:4px}
.tabel{overflow-x:auto;margin:12px 0;border:1px solid var(--lijn);border-radius:8px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:14px}
th,td{padding:7px 10px;border-bottom:1px solid var(--lijn);white-space:nowrap}
th{background:var(--kop);font-weight:600;text-align:left}
tr:last-child td{border-bottom:0}
.r{text-align:right}
main>p:nth-of-type(1),main>p:nth-of-type(2){color:var(--zacht)}
"""


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def markdown_naar_html(md: str, titel: str) -> str:
    """Kleine omzetter voor precies de Markdown die dit script zelf schrijft."""
    uit, regels, i = [], md.split("\n"), 0
    while i < len(regels):
        r = regels[i]
        if r.startswith("#"):
            n = len(r) - len(r.lstrip("#"))
            uit.append(f"<h{n}>{_inline(r[n:].strip())}</h{n}>")
        elif r.startswith("|"):
            blok = []
            while i < len(regels) and regels[i].startswith("|"):
                blok.append([c.strip() for c in regels[i].strip("|").split("|")])
                i += 1
            rechts = [c.endswith(":") for c in blok[1]]
            th = "".join(f'<th class="{"r" if rechts[j] else ""}">{_inline(c)}</th>' for j, c in enumerate(blok[0]))
            body = "".join("<tr>" + "".join(f'<td class="{"r" if rechts[j] else ""}">{_inline(c)}</td>'
                                            for j, c in enumerate(rij)) + "</tr>" for rij in blok[2:])
            uit.append(f'<div class="tabel"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>')
            continue
        elif r.startswith("- ") or re.match(r"\d+\. ", r):
            geordend = not r.startswith("- ")
            items = []
            while i < len(regels) and (regels[i].startswith("- ") if not geordend else re.match(r"\d+\. ", regels[i])):
                items.append(f"<li>{_inline(re.sub(r'^(- |\d+\. )', '', regels[i]))}</li>")
                i += 1
            tag = "ol" if geordend else "ul"
            uit.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue
        elif r.strip():
            uit.append(f"<p>{_inline(r)}</p>")
        i += 1
    return (f'<!doctype html><html lang="nl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(titel)}</title><style>{CSS}</style></head><body><main>"
            + "\n".join(uit) + "</main></body></html>")


# ---------------------------------------------------------------- bestanden

def schrijf_schone_data(data: Dataset, pad: Path):
    """Alle weken na opschonen, met puntkomma's en komma-decimalen zodat Excel (NL) hem direct opent."""
    def nl(x, dec=2):
        return "" if x is None else f"{x:.{dec}f}".replace(".", ",")
    with pad.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["week", "dimensie", "waarde", "impressies", "klikken", "ctr_pct", "uitgaven_eur",
                    "leads", "websiteconversies", "kosten_per_lead", "bron"])
        for r in data.rijen:
            ctr = r.klikken / r.impressies * 100 if r.impressies and r.klikken is not None else None
            cpl = r.spend / r.leads if r.leads and r.spend is not None else None
            w.writerow([r.week.isoformat(), r.dimensie, r.waarde, nl(r.impressies, 0), nl(r.klikken, 0), nl(ctr),
                        nl(r.spend), nl(r.leads, 0), nl(r.conversies, 0), nl(cpl), r.bron])


def schrijf(a: Analyse, data: Dataset, cfg: KlantConfig, gemaakt: datetime | None = None) -> dict[str, Path]:
    gemaakt = gemaakt or datetime.now()
    cfg.rapportmap.mkdir(parents=True, exist_ok=True)
    basis = cfg.rapportmap / f"{a.week:%Y-%m-%d}_weekrapport"
    md = maak_markdown(a, data, cfg, gemaakt)
    paden = {"markdown": basis.with_suffix(".md"), "html": basis.with_suffix(".html"),
             "data": cfg.rapportmap / "schone_data.csv"}
    paden["markdown"].write_text(md, encoding="utf-8")
    paden["html"].write_text(markdown_naar_html(md, f"Weekrapportage {a.klant} {a.week:%d-%m-%Y}"), encoding="utf-8")
    schrijf_schone_data(data, paden["data"])
    return paden
