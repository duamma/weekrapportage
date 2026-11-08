"""Exports samenvoegen, controleren en waar mogelijk automatisch corrigeren.

Alles wat het script aanpast of opmerkt, wordt vastgelegd als Melding en
komt in het rapport onder "Datakwaliteit". Er wordt niets stil veranderd.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from .config import KlantConfig
from .inlezen import LABEL, METRIEKEN, Export, ExportFout, Melding, Rij, normaliseer
from .opmaak import getal, pct, week_kort


@dataclass
class Dataset:
    rijen: list[Rij]
    meldingen: list[Melding]
    exports: list[Export]
    weekbron: dict[date, str]   # week -> exportbestand waar de cijfers vandaan komen


def _labelsleutel(s: str) -> str:
    """Sleutel om schrijfwijzen te vergelijken: '1.000+' en '1000+' -> '1000+'."""
    return re.sub(r"[\s.\-_,'’]", "", s.casefold())


def _fmt(m: str, x: float) -> str:
    return getal(x) if m != "spend" else f"€{getal(x)}"


def schoon_op(exports: list[Export], cfg: KlantConfig) -> Dataset:
    meldingen: list[Melding] = [m for e in exports for m in e.meldingen]

    # Oudste export eerst; bij overlap wint de nieuwste.
    exports = sorted(exports, key=lambda e: (max(e.weken), e.gegenereerd or date.min, e.pad.stat().st_mtime))

    _controleer_account(exports, cfg, meldingen)
    _vergelijk_opbouw(exports, meldingen)
    _normaliseer_labels(exports, cfg, meldingen)
    for e in exports:
        e.rijen = _verwijder_dubbelen(e, meldingen)

    # Welke export levert de cijfers voor welke week?
    weekbron: dict[date, str] = {}
    for e in exports:
        for w in e.weken:
            if w in weekbron:
                meldingen.append(Melding("info", f"De {week_kort(w)} staat in {weekbron[w]} én in {e.naam}; "
                                                 f"de cijfers uit {e.naam} (de nieuwste) zijn gebruikt.", e.naam, w))
            weekbron[w] = e.naam
    rijen = [r for e in exports for r in e.rijen if weekbron[r.week] == e.naam]

    _voeg_schrijfwijzen_samen(rijen, meldingen)
    _controleer_waarden(rijen, cfg, meldingen)
    _vul_ontbrekend_aan(rijen, meldingen)
    _controleer_totalen(rijen, meldingen)
    _controleer_weken(rijen, exports, meldingen)

    rijen.sort(key=lambda r: r.week)
    return Dataset(rijen=rijen, meldingen=meldingen, exports=exports, weekbron=weekbron)


# ---------------------------------------------------------------- stappen

def _controleer_account(exports, cfg, meldingen):
    for e in exports:
        acc = e.meta.get("account")
        if cfg.account and acc and normaliseer(acc) != normaliseer(cfg.account):
            raise ExportFout(f"{e.naam} is een export van account '{acc}', niet van '{cfg.account}'. "
                             f"Staat het bestand in de goede map ({cfg.exportmap})?")
        if cfg.account and not acc:
            meldingen.append(Melding("info", f"{e.naam} heeft geen regel 'Account:'; niet gecontroleerd of het de goede klant is.", e.naam))


def _vergelijk_opbouw(exports, meldingen):
    for vorige, e in zip(exports, exports[1:]):
        verschil = []
        nieuwe_meta = [k for k in e.meta if k not in vorige.meta]
        if e.koprij != vorige.koprij:
            extra = f" (extra regel '{nieuwe_meta[0].capitalize()}: …')" if nieuwe_meta else ""
            verschil.append(f"de kopregel staat op regel {e.koprij} in plaats van {vorige.koprij}{extra}")
        for intern, kop in e.kolomkoppen.items():
            oud = vorige.kolomkoppen.get(intern)
            if oud is None:
                verschil.append(f"nieuwe kolom '{kop}'")
            elif normaliseer(oud) != normaliseer(kop):
                verschil.append(f"kolom '{oud}' heet nu '{kop}'")
        for intern, kop in vorige.kolomkoppen.items():
            if intern not in e.kolomkoppen:
                verschil.append(f"kolom '{kop}' ontbreekt")
        oude_dims = {normaliseer(r.dimensie) for r in vorige.rijen}
        nieuwe_dims = sorted({r.dimensie for r in e.rijen if normaliseer(r.dimensie) not in oude_dims})
        if nieuwe_dims:
            verschil.append(f"nieuwe dimensie {', '.join(nieuwe_dims)}")
        if verschil:
            meldingen.append(Melding("info", f"{e.naam} is anders opgebouwd dan {vorige.naam}: "
                                             + "; ".join(verschil) + ". Automatisch opgevangen.", e.naam))
        if e.ongebruikte_kolommen:
            meldingen.append(Melding("info", f"Kolommen niet gebruikt in {e.naam}: {', '.join(e.ongebruikte_kolommen)}.", e.naam))


def _normaliseer_labels(exports, cfg, meldingen):
    dim_alias = {normaliseer(k): v for k, v in cfg.dimensies.items()}
    labelmap = {normaliseer(d): {normaliseer(o): n for o, n in m.items()} for d, m in cfg.labels.items()}
    teller = Counter()
    for e in exports:
        for r in e.rijen:
            r.dimensie = dim_alias.get(normaliseer(r.dimensie), " ".join(r.dimensie.split()))
            oud = " ".join(r.waarde.split())
            nieuw = labelmap.get(normaliseer(r.dimensie), {}).get(normaliseer(oud), oud)
            if nieuw != oud:
                teller[(e.naam, r.dimensie, oud, nieuw)] += 1
            r.waarde = nieuw
    for (bron, d, oud, nieuw), n in teller.items():
        meldingen.append(Melding("gecorrigeerd", f"'{oud}' ({d}) gelezen als '{nieuw}' ({n}× in {bron}), "
                                                 f"zodat het als hetzelfde segment wordt vergeleken.", bron))


def _verwijder_dubbelen(e: Export, meldingen) -> list[Rij]:
    uniek: dict[tuple, Rij] = {}
    for r in e.rijen:
        k = r.sleutel()
        eerder = uniek.get(k)
        if eerder is None:
            uniek[k] = r
        elif eerder.cijfers() == r.cijfers():
            meldingen.append(Melding("gecorrigeerd", f"Dubbele regel verwijderd: {r.dimensie} · {r.waarde}, {week_kort(r.week)} "
                                                     f"(regel {r.regel} is een kopie van regel {eerder.regel}).", e.naam, r.week))
        else:
            meldingen.append(Melding("controleren", f"Twee verschillende regels voor {r.dimensie} · {r.waarde}, {week_kort(r.week)} "
                                                    f"(regels {eerder.regel} en {r.regel}). De laatste is gebruikt; controleer de export.", e.naam, r.week))
            uniek[k] = r
    return list(uniek.values())


def _voeg_schrijfwijzen_samen(rijen: list[Rij], meldingen):
    """Vangnet voor varianten die niet in de config staan ('Security/Risk' vs 'Security / Risk')."""
    for soort in ("dimensie", "waarde"):
        groepen: dict[tuple, dict[str, date]] = defaultdict(dict)
        for r in rijen:
            context = "" if soort == "dimensie" else r.dimensie
            label = getattr(r, soort)
            k = (context, _labelsleutel(label))
            groepen[k][label] = max(groepen[k].get(label, date.min), r.week)
        for (context, _), varianten in groepen.items():
            if len(varianten) < 2:
                continue
            winnaar = max(varianten, key=lambda l: varianten[l])  # schrijfwijze uit de nieuwste week
            for r in rijen:
                if (soort == "waarde" and r.dimensie != context):
                    continue
                if getattr(r, soort) in varianten:
                    setattr(r, soort, winnaar)
            andere = ", ".join(f"'{v}'" for v in varianten if v != winnaar)
            waar = f" ({context})" if context else ""
            meldingen.append(Melding("gecorrigeerd", f"{andere}{waar} samengevoegd met '{winnaar}': zelfde segment, andere schrijfwijze. "
                                                     f"Leg dit vast onder [labels] in de klantconfiguratie."))


def _controleer_waarden(rijen: list[Rij], cfg, meldingen):
    tol = cfg.drempels["ctr_tolerantie_pp"] / 100
    for r in rijen:
        naam = f"{r.dimensie} · {r.waarde}, {week_kort(r.week)}"
        for m in METRIEKEN:
            v = getattr(r, m)
            if v is not None and v < 0:
                meldingen.append(Melding("controleren", f"Negatieve {LABEL[m].lower()} ({_fmt(m, v)}) bij {naam}.", r.bron, r.week))
        if r.impressies is not None and r.klikken is not None and r.klikken > r.impressies:
            meldingen.append(Melding("controleren", f"Meer klikken dan impressies bij {naam}.", r.bron, r.week))
        if r.ctr_export is not None and r.impressies and r.klikken is not None:
            berekend = r.klikken / r.impressies
            if abs(berekend - r.ctr_export) > tol:
                meldingen.append(Melding("gecorrigeerd", f"CTR van {naam} staat in de export als {pct(r.ctr_export)}, maar klikken ÷ impressies "
                                                         f"= {pct(berekend)}. De berekende CTR is gebruikt (het script rekent CTR altijd zelf uit).",
                                         r.bron, r.week))


def _per_week_dim(rijen):
    groep: dict[date, dict[str, list[Rij]]] = defaultdict(lambda: defaultdict(list))
    for r in rijen:
        groep[r.week][r.dimensie].append(r)
    return groep


def _vul_ontbrekend_aan(rijen: list[Rij], meldingen):
    """Elke dimensie verdeelt hetzelfde totaal. Mist er in één dimensie precies één
    waarde, dan is die af te leiden uit het totaal van een complete andere dimensie."""
    for w, dims in _per_week_dim(rijen).items():
        for m in METRIEKEN:
            alle = [getattr(r, m) for rs in dims.values() for r in rs]
            if all(v is None for v in alle):
                continue  # kolom zit niet in deze export
            compleet = {d: sum(getattr(r, m) for r in rs) for d, rs in dims.items()
                        if all(getattr(r, m) is not None for r in rs)}
            for d, rs in dims.items():
                missend = [r for r in rs if getattr(r, m) is None]
                if not missend:
                    continue
                referentie = next(((rd, t) for rd, t in compleet.items() if rd != d), None)
                if len(missend) == 1 and referentie:
                    rd, totaal = referentie
                    rest = totaal - sum(getattr(r, m) for r in rs if getattr(r, m) is not None)
                    if rest >= -0.005:
                        r = missend[0]
                        setattr(r, m, round(max(rest, 0.0), 2))
                        meldingen.append(Melding("gecorrigeerd", f"{LABEL[m]} ontbraken bij {d} · {r.waarde}, {week_kort(w)}. Afgeleid uit het "
                                                                 f"totaal van {rd} ({_fmt(m, totaal)}): {_fmt(m, getattr(r, m))}.", r.bron, w))
                        continue
                for r in missend:
                    meldingen.append(Melding("controleren", f"{LABEL[m]} ontbreken bij {d} · {r.waarde}, {week_kort(w)} en zijn niet af te leiden; telt als 0.",
                                             r.bron, w))


def _controleer_totalen(rijen: list[Rij], meldingen):
    for w, dims in _per_week_dim(rijen).items():
        if len(dims) < 2:
            continue
        for m in METRIEKEN:
            sommen = {d: sum(getattr(r, m) for r in rs) for d, rs in dims.items()
                      if all(getattr(r, m) is not None for r in rs)}
            if len(sommen) < 2:
                continue
            hoog, laag = max(sommen.values()), min(sommen.values())
            if hoog - laag > max(0.01, 0.005 * hoog):
                lijst = ", ".join(f"{d} {_fmt(m, s)}" for d, s in sommen.items())
                meldingen.append(Melding("controleren", f"Totaal {LABEL[m].lower()} verschilt per dimensie in de {week_kort(w)}: {lijst}. "
                                                        f"Elke dimensie hoort op hetzelfde totaal uit te komen; mogelijk mist of dubbelt er een regel.",
                                         week=w))


def _controleer_weken(rijen: list[Rij], exports: list[Export], meldingen):
    weken = sorted({r.week for r in rijen})
    for a, b in zip(weken, weken[1:]):
        gat = (b - a).days
        if gat % 7:
            meldingen.append(Melding("controleren", f"De weken beginnen niet op dezelfde dag ({a:%d-%m} en {b:%d-%m}). Vergelijkingen kunnen scheef zijn.", week=b))
        elif gat > 7:
            missend = [week_kort(a + timedelta(days=7 * i)) for i in range(1, gat // 7)]
            meldingen.append(Melding("controleren", f"Er ontbreekt data voor: {', '.join(missend)}. Zet die export erbij als je hem hebt.", week=b))
    for e in exports:
        g = e.gegenereerd
        if g is None:
            continue
        for w in e.weken:
            if g < w + timedelta(days=7):
                meldingen.append(Melding("controleren", f"{e.naam} is gemaakt op {g:%d-%m-%Y}, vóór het einde van de {week_kort(w)}. "
                                                        f"De cijfers van die week zijn waarschijnlijk onvolledig; draai het rapport opnieuw met een latere export.",
                                         e.naam, w))
