"""Cijfers per week en per segment, en de regels die daar signalen en adviezen uit halen.

Alle regels zijn vaste, uitlegbare regels met drempels uit de klantconfiguratie.
Dezelfde data geeft dus altijd hetzelfde rapport.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from .config import KlantConfig
from .inlezen import METRIEKEN, ExportFout
from .opmaak import eur, factor, opsomming, pct, pct_verschil, verandering, weekperiode
from .opschonen import Dataset

KPI_TEKST = {
    "leads": {"meervoud": "leads", "enkel": "lead", "kosten": "kosten per lead", "Kosten": "Kosten per lead"},
    "conversies": {"meervoud": "websiteconversies", "enkel": "websiteconversie",
                   "kosten": "kosten per conversie", "Kosten": "Kosten per conversie"},
}


@dataclass
class Cijfers:
    impressies: float = 0.0
    klikken: float = 0.0
    spend: float = 0.0
    leads: float = 0.0
    conversies: float = 0.0

    def tel(self, bron) -> "Cijfers":
        for m in METRIEKEN:
            v = getattr(bron, m)
            if v is not None:
                setattr(self, m, getattr(self, m) + v)
        return self

    @property
    def ctr(self):
        return self.klikken / self.impressies if self.impressies else None

    @property
    def cpc(self):
        return self.spend / self.klikken if self.klikken else None

    def aantal(self, kpi: str) -> float:
        return getattr(self, kpi)

    def kosten_per(self, kpi: str):
        n = getattr(self, kpi)
        return self.spend / n if n else None


@dataclass
class Segment:
    dimensie: str
    waarde: str
    nu: Cijfers | None
    vorig: Cijfers | None
    periode: Cijfers
    n_weken: int
    aandeel_nu: float | None
    aandeel_vorig: float | None
    nieuw: bool = False
    redenen: list[str] = field(default_factory=list)
    categorie: str | None = None   # uitsluiten | afschalen | kwaliteit | opschalen
    kort: str = ""

    @property
    def naam(self) -> str:
        return f"{self.dimensie} · {self.waarde}"


@dataclass
class Punt:
    onderwerp: str
    tekst: str
    prioriteit: int = 2
    samenvatting: str = ""


@dataclass
class Analyse:
    klant: str
    kpi: str
    week: date
    vorige: date | None
    weken: list[date]
    totaal: Cijfers
    totaal_vorig: Cijfers | None
    totaal_periode: Cijfers
    gemiddelde_eerder: Cijfers | None
    dimensies: list[str]
    segmenten: dict[str, list[Segment]]
    verdwenen: list[Segment]
    nieuwe_dimensies: list[str]
    heeft_conversies: bool
    veranderingen: list[str] = field(default_factory=list)
    aandacht: list[Punt] = field(default_factory=list)
    kansen: list[Punt] = field(default_factory=list)
    acties: list[str] = field(default_factory=list)
    kort: list[str] = field(default_factory=list)
    account_actie: str | None = None
    reeks: list = field(default_factory=list)   # [(week, Cijfers)] voor de grafiek

    @property
    def t(self):
        return KPI_TEKST[self.kpi]


# ---------------------------------------------------------------- berekenen

def _weektotalen(data: Dataset) -> dict[date, Cijfers]:
    """Totaal per week = som van één dimensie (dimensies overlappen, dus nooit optellen over dimensies)."""
    groep = defaultdict(lambda: defaultdict(list))
    for r in data.rijen:
        groep[r.week][r.dimensie].append(r)
    dekking = Counter(d for dims in groep.values() for d in dims)
    totalen = {}
    for w, dims in groep.items():
        volgorde = sorted(dims, key=lambda d: (-dekking[d], d))
        c = Cijfers()
        for m in METRIEKEN:
            for d in volgorde:
                waarden = [getattr(r, m) for r in dims[d]]
                if all(v is not None for v in waarden):
                    setattr(c, m, float(sum(waarden)))
                    break
            else:
                setattr(c, m, float(sum(getattr(r, m) or 0 for r in dims[volgorde[0]])))
        totalen[w] = c
    return totalen


def analyseer(data: Dataset, cfg: KlantConfig, week: date | None = None) -> Analyse:
    alle_weken = sorted({r.week for r in data.rijen})
    if not alle_weken:
        raise ExportFout("Er zijn geen bruikbare regels gevonden.")
    if week is None:
        week = alle_weken[-1]
    elif week not in alle_weken:
        raise ExportFout(f"Week {week:%Y-%m-%d} zit niet in de data. Beschikbaar: "
                         + ", ".join(f"{w:%Y-%m-%d}" for w in alle_weken))
    weken = [w for w in alle_weken if w <= week]
    vorige = weken[-2] if len(weken) > 1 else None

    totalen = _weektotalen(data)
    seg = defaultdict(lambda: defaultdict(dict))    # week -> dim -> waarde -> Cijfers
    dims_volgorde: list[str] = []
    for r in data.rijen:
        if r.week > week:
            continue
        seg[r.week][r.dimensie][r.waarde] = Cijfers().tel(r)
        if r.dimensie not in dims_volgorde:
            dims_volgorde.append(r.dimensie)

    periode_totaal = Cijfers()
    for w in weken:
        periode_totaal.tel(totalen[w])
    eerder = weken[:-1]
    gemiddelde = None
    if eerder:
        gemiddelde = Cijfers()
        for w in eerder:
            gemiddelde.tel(totalen[w])
        for m in METRIEKEN:
            setattr(gemiddelde, m, getattr(gemiddelde, m) / len(eerder))

    def maak_segment(d, v):
        per = Cijfers()
        n = 0
        for w in weken:
            if v in seg[w].get(d, {}):
                per.tel(seg[w][d][v])
                n += 1
        nu = seg[week].get(d, {}).get(v)
        vorig = seg[vorige].get(d, {}).get(v) if vorige else None
        t_nu, t_vorig = totalen[week], totalen.get(vorige) if vorige else None
        return Segment(
            dimensie=d, waarde=v, nu=nu, vorig=vorig, periode=per, n_weken=n,
            aandeel_nu=(nu.spend / t_nu.spend) if nu and t_nu.spend else None,
            aandeel_vorig=(vorig.spend / t_vorig.spend) if vorig and t_vorig and t_vorig.spend else None,
            nieuw=(n == 1),
        )

    dims_nu = [d for d in dims_volgorde if d in seg[week]]
    segmenten = {d: [maak_segment(d, v) for v in seg[week][d]] for d in dims_nu}
    verdwenen = []
    if vorige:
        for d, waarden in seg[vorige].items():
            for v in waarden:
                if v not in seg[week].get(d, {}):
                    verdwenen.append(maak_segment(d, v))
    nieuwe_dims = [d for d in dims_nu if not any(d in seg[w] for w in weken[:-1])] if vorige else []

    a = Analyse(
        klant=cfg.naam, kpi=cfg.primaire_kpi, week=week, vorige=vorige, weken=weken,
        totaal=totalen[week], totaal_vorig=totalen.get(vorige) if vorige else None,
        totaal_periode=periode_totaal, gemiddelde_eerder=gemiddelde,
        dimensies=dims_nu, segmenten=segmenten, verdwenen=verdwenen, nieuwe_dimensies=nieuwe_dims,
        heeft_conversies=any(r.conversies is not None for r in data.rijen),
    )
    a.reeks = [(w, totalen[w]) for w in weken]
    _account_regels(a, cfg, [totalen[w] for w in weken])
    _segment_regels(a, cfg)
    _veranderingen(a, cfg)
    _acties(a, cfg, data)
    _in_het_kort(a)
    return a


# ---------------------------------------------------------------- regels: totaal

def _account_regels(a: Analyse, cfg: KlantConfig, reeks: list[Cijfers]):
    dr, t, v, kpi = cfg.drempels, a.totaal, a.totaal_vorig, a.kpi
    a.account_actie = None
    if v is None:
        return
    d_spend = verandering(t.spend, v.spend)
    k_nu, k_vorig = t.kosten_per(kpi), v.kosten_per(kpi)
    d_kosten = verandering(k_nu, k_vorig)
    kosten_tekst = f"{eur(k_vorig)} → {eur(k_nu)}"

    if d_spend is not None and abs(d_spend) >= dr["grote_verandering_pct"] / 100:
        daling = d_spend < 0
        trend = ""
        eerdere = [c.spend for c in reeks[:-1]]
        if len(eerdere) >= 2:
            stijgend = all(x < y for x, y in zip(eerdere, eerdere[1:]))
            dalend = all(x > y for x, y in zip(eerdere, eerdere[1:]))
            if daling and stijgend:
                trend = f" Daarvoor stegen de uitgaven {len(eerdere) - 1} weken op rij, dus dit is een trendbreuk."
            elif not daling and dalend:
                trend = f" Daarvoor daalden de uitgaven {len(eerdere) - 1} weken op rij."
        a.aandacht.append(Punt(
            "Totaal budget",
            f"De uitgaven {'daalden' if daling else 'stegen'} {pct_verschil(abs(d_spend)).lstrip('+')} "
            f"({eur(v.spend, None)} → {eur(t.spend, None)}). Impressies {pct_verschil(verandering(t.impressies, v.impressies))}, "
            f"klikken {pct_verschil(verandering(t.klikken, v.klikken))}, {a.t['meervoud']} "
            f"{pct_verschil(verandering(t.aantal(kpi), v.aantal(kpi)))}.{trend}", 1,
            f"de uitgaven {'daalden' if daling else 'stegen'} {pct_verschil(abs(d_spend)).lstrip('+')} ten opzichte van vorige week"))
        if daling:
            if d_kosten is not None and d_kosten >= dr["kpi_verandering_pct"] / 100:
                a.account_actie = (f"**Zoek uit waarom de uitgaven {pct_verschil(-d_spend).lstrip('+')} lager zijn.** Ga in de "
                                    f"advertentietool na of een dagbudget is verlaagd of een campagne is gepauzeerd of afgelopen. "
                                    f"De {a.t['kosten']} stegen ook ({kosten_tekst}), dus kijk welke campagne geraakt is voordat je het budget terugzet.")
            else:
                oordeel = "verbeterden zelfs" if d_kosten is not None and d_kosten <= -0.10 else "bleven ongeveer gelijk"
                a.account_actie = (f"**Zoek vandaag uit waarom de uitgaven {pct_verschil(-d_spend).lstrip('+')} lager zijn.** Ga in de "
                                    f"advertentietool na of een dagbudget is verlaagd of een campagne is gepauzeerd of afgelopen. "
                                    f"De {a.t['kosten']} {oordeel} ({kosten_tekst}), dus de resultaten zijn geen reden om minder uit te geven. "
                                    f"Was de verlaging niet bewust, zet het budget dan terug.")
        else:
            gevolg = (f"De {a.t['kosten']} stegen mee ({kosten_tekst}): het extra budget levert relatief minder op."
                      if d_kosten is not None and d_kosten >= dr["kpi_verandering_pct"] / 100
                      else f"De {a.t['kosten']} bleven op peil ({kosten_tekst}).")
            a.account_actie = f"**Ga na of de hogere uitgaven bewust zijn.** {gevolg}"

    if d_kosten is not None and d_kosten >= dr["kpi_verandering_pct"] / 100:
        a.aandacht.append(Punt("Kosten per resultaat",
                               f"De {a.t['kosten']} stegen {pct_verschil(d_kosten)} ({kosten_tekst}). De segmenttabellen laten zien waar dat zit.", 1,
                               f"de {a.t['kosten']} stegen {pct_verschil(d_kosten)}"))
    elif d_kosten is not None and d_kosten <= -dr["kpi_verandering_pct"] / 100:
        a.kansen.append(Punt("Kosten per resultaat", f"De {a.t['kosten']} daalden {pct_verschil(d_kosten)} ({kosten_tekst}).", 2))

    if a.heeft_conversies and kpi == "leads" and v.conversies > 0 and t.conversies == 0:
        a.aandacht.append(Punt("Websiteconversies", f"Geen enkele websiteconversie deze week (vorige week {v.conversies:.0f}). "
                                                    "Controleer of de conversietracking nog werkt.", 1, "geen enkele websiteconversie deze week"))


# ---------------------------------------------------------------- regels: segmenten

def _segment_regels(a: Analyse, cfg: KlantConfig):
    dr, kpi, t = cfg.drempels, a.kpi, a.t
    acc_week = a.totaal.kosten_per(kpi)
    acc_per = a.totaal_periode.kosten_per(kpi)
    secundair = a.heeft_conversies and kpi == "leads"
    n_per = len(a.weken)

    for d, segs in a.segmenten.items():
        laagste_ctr = min((s for s in segs if s.nu.impressies), key=lambda s: s.nu.ctr, default=None)
        for s in segs:
            nu, per = s.nu, s.periode
            kosten_per = per.kosten_per(kpi)

            # 1. Geld zonder resultaat deze week
            if nu.spend >= dr["min_uitgaven_week"] and nu.aantal(kpi) == 0:
                aandeel = f" ({pct(s.aandeel_nu, 0)} van het budget)" if s.aandeel_nu else ""
                s.redenen.append(f"{eur(nu.spend, None)} uitgegeven{aandeel} zonder één {t['enkel']}")
                s.categorie = "uitsluiten"
                s.kort = f"{eur(nu.spend, None)} deze week, 0 {t['meervoud']}"

            # 2. Structureel te duur (over de hele periode)
            if s.n_weken >= 2 and per.spend >= dr["min_uitgaven_periode"]:
                if per.aantal(kpi) == 0:
                    s.redenen.append(f"in {s.n_weken} weken {eur(per.spend, None)} uitgegeven zonder {t['meervoud']}")
                    s.categorie = s.categorie or "afschalen"
                    s.kort = s.kort or f"{eur(per.spend, None)} in {s.n_weken} weken, 0 {t['meervoud']}"
                elif acc_per and kosten_per >= dr["factor_duur"] * acc_per:
                    s.redenen.append(f"{t['kosten']} over {s.n_weken} weken {eur(kosten_per)}, "
                                     f"{factor(kosten_per / acc_per)} het gemiddelde ({eur(acc_per)})")
                    s.categorie = s.categorie or "afschalen"
                    s.kort = s.kort or f"{eur(kosten_per)} per {t['enkel']} over {s.n_weken} weken, {factor(kosten_per / acc_per)} het gemiddelde"

            # 3. Leads, maar nooit een websiteconversie
            if secundair and s.n_weken >= dr["min_weken_zonder_conversie"] and per.spend >= dr["min_uitgaven_periode"] \
                    and per.conversies == 0:
                s.redenen.append(f"in {s.n_weken} weken geen enkele websiteconversie ({eur(per.spend, None)} uitgegeven)")
                if s.categorie is None:
                    if kosten_per is not None and acc_per and kosten_per <= dr["factor_kwaliteitscheck"] * acc_per:
                        s.categorie = "kwaliteit"
                        s.kort = f"{eur(per.spend, None)}, {per.leads:.0f} leads en 0 websiteconversies in {s.n_weken} weken"
                    else:
                        s.categorie = "afschalen"
                        s.kort = f"0 websiteconversies in {s.n_weken} weken"

            # 4. Winnaar: duidelijk goedkoper dan gemiddeld, met genoeg volume
            k_nu = nu.kosten_per(kpi)
            if s.categorie is None and acc_week and nu.aantal(kpi) >= dr["min_leads_winnaar"] \
                    and k_nu <= dr["factor_goedkoop"] * acc_week:
                delen = [f"{t['kosten']} {eur(k_nu)} tegen {eur(acc_week)} gemiddeld "
                         f"({nu.aantal(kpi):.0f} van de {a.totaal.aantal(kpi):.0f} {t['meervoud']})"]
                if s.n_weken >= 2 and kosten_per is not None and acc_per and kosten_per <= dr["factor_goedkoop"] * acc_per:
                    delen.append(f"en dat is structureel: {eur(kosten_per)} over {s.n_weken} weken tegen {eur(acc_per)} gemiddeld")
                elif s.n_weken == 1 and len(a.weken) > 1:
                    delen.append("eerste week met data, dus nog een voorzichtig signaal")
                if secundair and a.totaal.conversies and nu.conversies / a.totaal.conversies >= 0.5:
                    delen.append(f"levert {nu.conversies:.0f} van de {a.totaal.conversies:.0f} websiteconversies")
                s.redenen.append("; ".join(delen))
                s.categorie = "opschalen"
                s.kort = f"{eur(k_nu)} per {t['enkel']} tegen {eur(acc_week)} gemiddeld"

            if s.nieuw and s.categorie and len(a.weken) > 1:
                s.kort += " (eerste week met data)"
            if s.categorie in ("uitsluiten", "afschalen") and s is laagste_ctr and len(segs) > 2:
                s.redenen.append(f"laagste CTR van {d} ({pct(nu.ctr)})")

            if s.categorie in ("uitsluiten", "afschalen", "kwaliteit"):
                a.aandacht.append(Punt(s.naam, _zin(s.redenen), 1 if s.categorie == "uitsluiten" else 2, f"{s.naam}: {s.kort}"))
            elif s.categorie == "opschalen":
                a.kansen.append(Punt(s.naam, _zin(s.redenen), 2))

    if n_per == 1:
        a.aandacht.append(Punt("Eerste week", "Er is nog geen eerdere week om mee te vergelijken; signalen over trends komen vanaf volgende week.", 3,
                               "er is nog geen eerdere week om mee te vergelijken"))
    a.aandacht.sort(key=lambda p: p.prioriteit)


def _zin(delen: list[str]) -> str:
    tekst = "; ".join(delen)
    return tekst[0].upper() + tekst[1:] + "."


# ---------------------------------------------------------------- wat veranderde

def _veranderingen(a: Analyse, cfg: KlantConfig):
    t, v, kpi = a.totaal, a.totaal_vorig, a.kpi
    if v is None:
        return
    delen = []
    d_ctr, d_cpc = verandering(t.ctr, v.ctr), verandering(t.cpc, v.cpc)
    if d_ctr is not None and abs(d_ctr) >= 0.05:
        delen.append(f"de CTR {'steeg' if d_ctr > 0 else 'daalde'} van {pct(v.ctr)} naar {pct(t.ctr)}")
    if d_cpc is not None and abs(d_cpc) >= 0.05:
        delen.append(f"de kosten per klik {'stegen' if d_cpc > 0 else 'daalden'} van {eur(v.cpc)} naar {eur(t.cpc)}")
    if delen:
        a.veranderingen.append("**Efficiëntie:** " + opsomming(delen) + ".")

    drempel = cfg.drempels["verschuiving_pp"] / 100
    for d, segs in a.segmenten.items():
        if d in a.nieuwe_dimensies:
            continue
        met_beide = [s for s in segs if s.aandeel_nu is not None and s.aandeel_vorig is not None]
        if not any(abs(s.aandeel_nu - s.aandeel_vorig) >= drempel for s in met_beide):
            continue
        meer = sorted([s for s in met_beide if s.aandeel_nu - s.aandeel_vorig >= drempel / 2],
                      key=lambda s: s.aandeel_vorig - s.aandeel_nu)
        minder = sorted([s for s in met_beide if s.aandeel_vorig - s.aandeel_nu >= drempel / 2],
                        key=lambda s: s.aandeel_nu - s.aandeel_vorig)
        fmt = lambda s: f"{s.waarde} ({pct(s.aandeel_vorig, 0)} → {pct(s.aandeel_nu, 0)})"
        zin = f"**Budgetverdeling {d}:** "
        stukken = []
        if meer:
            stukken.append("meer naar " + opsomming([fmt(s) for s in meer]))
        if minder:
            stukken.append("minder naar " + opsomming([fmt(s) for s in minder]))
        zin += ", ".join(stukken) + "."
        effect = [f"{s.waarde} {eur(s.vorig.kosten_per(kpi))} → {eur(s.nu.kosten_per(kpi))}"
                  for s in meer if s.vorig.kosten_per(kpi) and s.nu.kosten_per(kpi)]
        if effect:
            zin += f" {a.t['Kosten']} bij de segmenten die meer kregen: {'; '.join(effect)}."
        a.veranderingen.append(zin)

    for d in a.nieuwe_dimensies:
        a.veranderingen.append(f"**Nieuw in de export:** de dimensie {d} ({opsomming([s.waarde for s in a.segmenten[d]])}). "
                               "Er is nog geen vorige week om mee te vergelijken.")
    nieuw = [s for d, segs in a.segmenten.items() if d not in a.nieuwe_dimensies for s in segs if s.nieuw]
    if nieuw:
        a.veranderingen.append(f"**Nieuwe segmenten:** {opsomming([s.naam for s in nieuw])}.")
    if a.verdwenen:
        a.veranderingen.append(f"**Niet meer in de export:** {opsomming([s.naam for s in a.verdwenen])}. "
                               "Is de targeting aangepast, of ontbreekt er iets in de export?")


# ---------------------------------------------------------------- adviezen

def _acties(a: Analyse, cfg: KlantConfig, data: Dataset):
    alle = [s for segs in a.segmenten.values() for s in segs]
    per_cat = lambda c: [s for s in alle if s.categorie == c]
    lijst = lambda segs: "; ".join(f"**{s.waarde}** ({s.dimensie}): {s.kort}" for s in segs)
    acties = []

    if a.account_actie:
        acties.append(a.account_actie)
    if per_cat("uitsluiten"):
        acties.append(f"**Sluit uit of verlaag het bod fors:** {lijst(per_cat('uitsluiten'))}.")
    if per_cat("afschalen"):
        acties.append(f"**Verlaag het budget voor:** {lijst(per_cat('afschalen'))}.")
    if per_cat("opschalen"):
        segs = per_cat("opschalen")
        acties.append(f"**Geef meer budget aan:** {lijst(segs)}. Doe het stap voor stap (bijv. +20% per week) "
                      f"en kijk of de {a.t['kosten']} onder het gemiddelde blijven"
                      + (". Signalen uit een nieuwe dimensie zijn na één week nog voorlopig." if any(s.nieuw for s in segs) and len(a.weken) > 1 else "."))
    if per_cat("kwaliteit"):
        acties.append(f"**Vraag sales hoe goed de leads zijn uit:** {lijst(per_cat('kwaliteit'))}. Die leads kosten niet meer dan "
                      "gemiddeld, maar leiden nooit tot een websiteconversie. Zijn het slechte leads, verlaag dan ook hier het budget.")
    controleren = [m for m in data.meldingen if m.niveau == "controleren" and (m.week is None or m.week in (a.week, a.vorige))]
    if controleren:
        acties.append(f"**Controleer de data:** {len(controleren)} punt(en) onder *Datakwaliteit → Controleren* "
                      "kunnen de cijfers van deze of vorige week beïnvloeden.")
    if not acties:
        acties.append("Geen grote afwijkingen. Laat de campagnes ongewijzigd draaien en kijk volgende week opnieuw.")
    a.acties = acties[: int(cfg.drempels["max_acties"])]


def _in_het_kort(a: Analyse):
    t, v, kpi = a.totaal, a.totaal_vorig, a.kpi
    def met(nu, vorig):
        d = verandering(nu, vorig)
        if d is None:
            return ""
        return " (gelijk)" if round(d * 100) == 0 else f" ({pct_verschil(d)})"
    zin = (f"{eur(t.spend, None)} uitgegeven{met(t.spend, v.spend if v else None)}, {t.aantal(kpi):.0f} {a.t['meervoud']}"
           f"{met(t.aantal(kpi), v.aantal(kpi) if v else None)}, {a.t['kosten']} {eur(t.kosten_per(kpi))}"
           f"{met(t.kosten_per(kpi), v.kosten_per(kpi) if v else None)}")
    if a.heeft_conversies and kpi == "leads":
        zin += f", {t.conversies:.0f} websiteconversies{met(t.conversies, v.conversies if v else None)}"
    a.kort.append(zin + ".")
    if a.account_actie and a.aandacht and a.aandacht[0].onderwerp == "Totaal budget":
        a.kort.append(f"**Eerst doen:** {a.aandacht[0].samenvatting}. Zoek uit of dat bewust was (zie advies 1).")
    segment_punten = [p for p in a.aandacht if "·" in p.onderwerp]
    if segment_punten:
        aantal = f"{len(segment_punten)} segmenten leveren" if len(segment_punten) > 1 else "1 segment levert"
        a.kort.append(f"**Aandacht:** {aantal} te weinig op voor wat ze kosten. Het duidelijkst: "
                      f"{segment_punten[0].samenvatting}.")
    elif a.aandacht and not a.account_actie:
        a.kort.append(f"**Aandacht:** {a.aandacht[0].samenvatting or a.aandacht[0].tekst}.")
    seg_kansen = [p for p in a.kansen if "·" in p.onderwerp]
    if seg_kansen:
        a.kort.append(f"**Kans:** {opsomming([p.onderwerp for p in seg_kansen])} {'leveren' if len(seg_kansen) > 1 else 'levert'} "
                      f"{a.t['meervoud']} duidelijk goedkoper dan gemiddeld.")
    elif a.kansen:
        a.kort.append(f"**Positief:** {a.kansen[0].tekst}")
