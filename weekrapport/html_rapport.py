"""HTML-rapport in huisstijl, met KPI-kaarten, weekgrafiek, sorteerbare tabellen en PDF-export.

Huisstijl (kleuren en fonts) staat bovenaan in HUISSTIJL; pas die aan voor een andere stijl.
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

from .opmaak import eur, getal, pct, pct_verschil, verandering, weekperiode, MAANDEN

HUISSTIJL = {
    "inkt": "#0F171C",       # donker: kop, tekst
    "petrol": "#004B4B",     # primair accent
    "petrol_donker": "#003131",
    "mint": "#8CDCA5",       # accent op donker
    "lila": "#D7C8FF",
    "creme": "#F6F5F1",      # achtergrond
    "grijs": "#5C6669",
    "grijs_licht": "#A8B0B2",
    "lijn": "#E2E1DD",
    "font_tekst": "'Inter Tight', Arial, sans-serif",
    "font_cijfer": "'Source Serif 4', Georgia, serif",
}
FONTS = ("https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700"
         "&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap")


def _css() -> str:
    h = HUISSTIJL
    return f"""
:root{{--inkt:{h['inkt']};--petrol:{h['petrol']};--petrol-d:{h['petrol_donker']};--mint:{h['mint']};--lila:{h['lila']};
--creme:{h['creme']};--grijs:{h['grijs']};--grijs-l:{h['grijs_licht']};--lijn:{h['lijn']};--wit:#fff;
--tekst:{h['font_tekst']};--cijfer:{h['font_cijfer']}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--creme);color:var(--inkt);font:15px/1.55 var(--tekst)}}
.hero{{background:var(--inkt);color:var(--creme);padding:40px 16px 32px}}
.wrap{{max-width:1040px;margin:0 auto}}
main.wrap{{padding:0 16px 64px}}
.overline{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-weight:600;color:var(--petrol)}}
.hero .overline{{color:var(--mint)}}
.hero h1{{font:400 clamp(34px,6vw,54px)/1.05 var(--cijfer);margin:10px 0 12px;letter-spacing:-.01em}}
.hero h1 em{{font-style:normal;color:var(--mint)}}
.hero p{{color:var(--grijs-l);margin:4px 0;max-width:760px}}
.knoppen{{margin-top:18px;display:flex;gap:8px;flex-wrap:wrap}}
.knop{{font:600 13px var(--tekst);border-radius:999px;padding:8px 16px;border:1px solid var(--mint);background:var(--mint);color:var(--inkt);cursor:pointer;text-decoration:none}}
.knop.lijn{{background:transparent;color:var(--mint)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:-1px 0 0;padding:24px 0 8px}}
.kpi{{background:var(--wit);border:1px solid var(--lijn);border-radius:14px;padding:16px 18px}}
.kpi .label{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--grijs);font-weight:600}}
.kpi .waarde{{font:400 38px/1.1 var(--cijfer);margin:6px 0 4px}}
.kpi .sub{{font-size:13px;color:var(--grijs)}}
.chip{{display:inline-block;font-weight:600;font-size:12px;border-radius:999px;padding:2px 8px;margin-right:6px}}
.chip.goed{{background:#DDF4E4;color:#1E5B33}}.chip.slecht{{background:#F4DEDE;color:#7A1F1F}}.chip.neutraal{{background:var(--lijn);color:var(--grijs)}}
.grafieken{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:12px 0}}
.grafiek{{background:var(--wit);border:1px solid var(--lijn);border-radius:14px;padding:14px 16px}}
.grafiek h4{{margin:0 0 6px;font-size:13px;font-weight:600;color:var(--grijs)}}
.grafiek svg{{width:100%;height:auto;display:block}}
h2{{font:600 26px/1.2 var(--tekst);margin:44px 0 14px;letter-spacing:-.01em}}
h2::before{{content:attr(data-nr);display:block;font:400 18px var(--cijfer);color:var(--petrol);margin-bottom:2px}}
h3{{font-size:16px;margin:22px 0 8px}}
p{{margin:8px 0}} ul,ol{{padding-left:22px;margin:8px 0}} li{{margin:7px 0}} strong{{font-weight:600}}
ol li::marker{{font-family:var(--cijfer);color:var(--petrol);font-weight:600}}
code{{font:13px ui-monospace,Menlo,monospace;background:var(--lijn);padding:1px 5px;border-radius:4px}}
.blok{{background:var(--wit);border:1px solid var(--lijn);border-radius:14px;padding:6px 20px}}
.tabel{{overflow-x:auto;margin:10px 0;border:1px solid var(--lijn);border-radius:12px;background:var(--wit)}}
table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:14px}}
th,td{{padding:8px 12px;border-bottom:1px solid var(--lijn);white-space:nowrap}}
th{{background:var(--petrol);color:var(--creme);font-weight:600;text-align:left;cursor:pointer;user-select:none}}
th:hover{{background:var(--petrol-d)}} th.r,td.r{{text-align:right}}
th[aria-sort]::after{{content:" ↕";opacity:.5}} th[aria-sort=ascending]::after{{content:" ↑";opacity:1}} th[aria-sort=descending]::after{{content:" ↓";opacity:1}}
tr:last-child td{{border-bottom:0}} tbody tr:hover{{background:#FAFAF7}}
details{{margin:44px 0 0}} details>summary{{cursor:pointer;list-style:none}}
details>summary h2{{display:inline-block;margin:0}} details>summary::after{{content:"Toon / verberg";font-size:12px;color:var(--petrol);margin-left:12px;font-weight:600}}
footer{{color:var(--grijs);font-size:12px;margin-top:48px;border-top:1px solid var(--lijn);padding-top:12px}}
@media print{{
  @page{{size:A4;margin:14mm}}
  body{{background:#fff;font-size:12px}} .knoppen{{display:none}}
  .hero{{-webkit-print-color-adjust:exact;print-color-adjust:exact;padding:24px 20px}}
  th,.chip,.kpi{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  details>summary::after{{display:none}} .kpi,.grafiek,.tabel,tr,li{{break-inside:avoid}} h2{{break-after:avoid}}
  .tabel{{overflow:visible}} th,td{{padding:5px 7px;white-space:normal}}
}}
"""


JS = r"""
document.querySelectorAll('details').forEach(d => window.matchMedia('print').addEventListener('change', e => { if (e.matches) d.open = true; }));
window.addEventListener('beforeprint', () => document.querySelectorAll('details').forEach(d => d.open = true));
function getal(t){
  t = t.split('→').pop().replace(/[€%★⚠?\s]|pp/g,'').replace(/\./g,'').replace(',','.').replace('−','-');
  const x = parseFloat(t); return isNaN(x) ? null : x;
}
document.querySelectorAll('table').forEach(tabel => {
  tabel.querySelectorAll('th').forEach((th, i) => {
    th.setAttribute('aria-sort','none');
    th.addEventListener('click', () => {
      const op = th.getAttribute('aria-sort') !== 'descending';
      tabel.querySelectorAll('th').forEach(h => h.setAttribute('aria-sort','none'));
      th.setAttribute('aria-sort', op ? 'descending' : 'ascending');
      const body = tabel.tBodies[0], rijen = [...body.rows];
      rijen.sort((a, b) => {
        const x = a.cells[i].innerText, y = b.cells[i].innerText, gx = getal(x), gy = getal(y);
        let c = (gx !== null || gy !== null) ? ((gx ?? -Infinity) - (gy ?? -Infinity)) : x.localeCompare(y, 'nl');
        return op ? -c : c;
      });
      rijen.forEach(r => body.appendChild(r));
    });
  });
});
"""


def _chip(d: float | None, lager_is_beter: bool = False) -> str:
    if d is None:
        return ""
    if abs(d) < 0.02:
        soort = "neutraal"
    else:
        soort = "goed" if (d < 0) == lager_is_beter else "slecht"
    return f'<span class="chip {soort}">{pct_verschil(d)}</span>'


def _kpi_kaarten(a) -> str:
    t, v, kpi = a.totaal, a.totaal_vorig, a.kpi
    kaarten = [
        ("Uitgaven", eur(t.spend, None), verandering(t.spend, v.spend) if v else None, False, f"vorige week {eur(v.spend, None)}" if v else ""),
        (a.t["meervoud"].capitalize(), getal(t.aantal(kpi)), verandering(t.aantal(kpi), v.aantal(kpi)) if v else None, False,
         f"vorige week {getal(v.aantal(kpi))}" if v else ""),
        (a.t["Kosten"], eur(t.kosten_per(kpi)), verandering(t.kosten_per(kpi), v.kosten_per(kpi)) if v else None, True,
         f"vorige week {eur(v.kosten_per(kpi))}" if v else ""),
    ]
    if a.heeft_conversies and kpi == "leads":
        kaarten.append(("Websiteconversies", getal(t.conversies), verandering(t.conversies, v.conversies) if v else None, False,
                        f"vorige week {getal(v.conversies)}" if v else ""))
    else:
        kaarten.append(("CTR", pct(t.ctr), verandering(t.ctr, v.ctr) if v else None, False, f"vorige week {pct(v.ctr)}" if v else ""))
    return '<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="label">{html.escape(l)}</div><div class="waarde">{w}</div>'
        f'<div class="sub">{_chip(d, beter)}{html.escape(sub)}</div></div>' for l, w, d, beter, sub in kaarten) + "</div>"


def _staafgrafiek(titel: str, punten: list[tuple[str, float | None]], fmt) -> str:
    """Eenvoudige staafgrafiek als inline SVG; de laatste staaf (deze week) in petrol."""
    b, hoogte, links, onder = 320, 150, 6, 22
    waarden = [w or 0 for _, w in punten]
    maxw = max(waarden) or 1
    n = len(punten)
    breedte = (b - 2 * links) / n
    delen = []
    for i, (label, w) in enumerate(punten):
        h = (w or 0) / maxw * (hoogte - onder - 20)
        x = links + i * breedte + breedte * 0.18
        y = hoogte - onder - h
        kleur = "var(--petrol)" if i == n - 1 else "var(--mint)"
        delen.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{breedte * 0.64:.1f}" height="{h:.1f}" rx="4" fill="{kleur}">'
                     f'<title>{html.escape(label)}: {html.escape(fmt(w))}</title></rect>'
                     f'<text x="{x + breedte * 0.32:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="11" fill="var(--inkt)">{html.escape(fmt(w))}</text>'
                     f'<text x="{x + breedte * 0.32:.1f}" y="{hoogte - 6}" text-anchor="middle" font-size="11" fill="var(--grijs)">{html.escape(label)}</text>')
    return (f'<div class="grafiek"><h4>{html.escape(titel)}</h4><svg viewBox="0 0 {b} {hoogte}" role="img" aria-label="{html.escape(titel)}">'
            + "".join(delen) + "</svg></div>")


def _grafieken(a) -> str:
    if len(a.reeks) < 2:
        return ""
    lab = lambda w: f"{w.day} {MAANDEN[w.month - 1][:3]}"
    kpi = a.kpi
    return '<div class="grafieken">' + "".join([
        _staafgrafiek("Uitgaven per week", [(lab(w), c.spend) for w, c in a.reeks], lambda x: eur(x, 0)),
        _staafgrafiek(f"{a.t['meervoud'].capitalize()} per week", [(lab(w), c.aantal(kpi)) for w, c in a.reeks], getal),
        _staafgrafiek(f"{a.t['Kosten']} per week", [(lab(w), c.kosten_per(kpi)) for w, c in a.reeks], lambda x: eur(x, 0)),
    ]) + "</div>"


def _secties(body: str) -> str:
    """Nummer de hoofdstukken (01, 02, ...) en maak de naslag-secties inklapbaar."""
    stukken = re.split(r"(?=<h2>)", body)
    uit, nr = [stukken[0]], 0
    for st in stukken[1:]:
        nr += 1
        titel = re.match(r"<h2>(.*?)</h2>", st).group(1)
        st = st.replace("<h2>", f'<h2 data-nr="{nr:02d}">', 1)
        if titel in ("Details per segment", "Datakwaliteit", "Over dit rapport"):
            kop, rest = st.split("</h2>", 1)
            st = f"<details{' open' if titel == 'Details per segment' else ''}><summary>{kop}</h2></summary>{rest}</details>"
        uit.append(st)
    return "".join(uit)


def maak_html(a, md: str, cfg, gemaakt: datetime) -> str:
    from .rapport import markdown_naar_html  # pas hier importeren (voorkomt kringverwijzing)
    inhoud = md.split("## In het kort", 1)[1]
    body = _secties(markdown_naar_html("## In het kort" + inhoud))
    weeknr = a.week.isocalendar()[1]
    vergelijk = f"Vergeleken met {weekperiode(a.vorige)}. " if a.vorige else ""
    titel = f"Weekrapportage {a.klant} {a.week:%d-%m-%Y}"
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(titel)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet"><style>{_css()}</style></head><body>
<header class="hero"><div class="wrap">
<div class="overline">Weekrapportage · week {weeknr} · {html.escape(weekperiode(a.week))}</div>
<h1>Campagnes {html.escape(a.klant)}, <em>deze week.</em></h1>
<p>{html.escape(vergelijk)}{len(a.weken)} weken historie. Gemaakt op {gemaakt:%d-%m-%Y %H:%M}.</p>
<div class="knoppen"><button class="knop" onclick="window.print()">Opslaan als PDF</button>
<a class="knop lijn" href="#wat-ik-zou-doen">Naar de adviezen</a></div>
</div></header>
<main class="wrap">{_kpi_kaarten(a)}{_grafieken(a)}{body.replace('<h2 data-nr="04">', '<h2 id="wat-ik-zou-doen" data-nr="04">')}
<footer>Automatisch gemaakt met de weekrapportage-workflow (maak_rapport.py) · klant: {html.escape(cfg.sleutel)} ·
tabellen zijn sorteerbaar: klik op een kolomkop.</footer></main><script>{JS}</script></body></html>"""


def maak_pdf(html_pad: Path, pdf_pad: Path) -> bool:
    """Maakt een PDF met Playwright als dat geïnstalleerd is. Zo niet: gewoon overslaan
    (de knop 'Opslaan als PDF' in het HTML-rapport doet hetzelfde via de browser)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            pagina = browser.new_page()
            pagina.goto(Path(html_pad).resolve().as_uri(), wait_until="networkidle")
            pagina.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            pagina.pdf(path=str(pdf_pad), format="A4", print_background=True,
                       margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"})
            browser.close()
        return True
    except Exception:
        return False
