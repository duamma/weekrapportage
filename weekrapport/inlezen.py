"""Eén export (xlsx of csv) inlezen en omzetten naar vaste kolommen.

Het script zoekt zelf de kopregel, ongeacht hoeveel regels er boven staan,
en herkent kolommen aan hun naam (zie [kolommen] in de klantconfiguratie),
niet aan hun positie. Zo blijft het werken als een export anders is opgebouwd.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import VERPLICHTE_KOLOMMEN, KlantConfig

METRIEKEN = ("impressies", "klikken", "spend", "leads", "conversies")
GEHELE_GETALLEN = {"impressies", "klikken", "leads", "conversies"}
LABEL = {"impressies": "Impressies", "klikken": "Klikken", "spend": "Uitgaven",
         "leads": "Leads", "conversies": "Websiteconversies", "ctr": "CTR",
         "week": "Week", "dimensie": "Dimensie", "waarde": "Waarde"}
TOTAALREGELS = {"totaal", "total", "eindtotaal", "grand total", "totaal generaal"}


class ExportFout(Exception):
    """Een export kan niet worden gebruikt."""


@dataclass
class Melding:
    niveau: str            # "controleren" (mens moet kijken), "gecorrigeerd" (automatisch opgelost), "info"
    tekst: str
    bron: str = ""
    week: date | None = None


@dataclass
class Rij:
    week: date
    dimensie: str
    waarde: str
    impressies: float | None
    klikken: float | None
    spend: float | None
    leads: float | None
    conversies: float | None
    ctr_export: float | None
    bron: str
    regel: int

    def sleutel(self) -> tuple:
        return (self.week, self.dimensie, self.waarde)

    def cijfers(self) -> tuple:
        return tuple(getattr(self, m) for m in METRIEKEN)


@dataclass
class Export:
    pad: Path
    meta: dict[str, str]
    kolomkoppen: dict[str, str]   # interne naam -> kolomnaam zoals in de export
    koprij: int                   # regelnummer van de kopregel (1 = eerste regel)
    rijen: list[Rij]
    meldingen: list[Melding] = field(default_factory=list)
    ongebruikte_kolommen: list[str] = field(default_factory=list)

    @property
    def naam(self) -> str:
        return self.pad.name

    @property
    def weken(self) -> list[date]:
        return sorted({r.week for r in self.rijen})

    @property
    def gegenereerd(self) -> date | None:
        for sleutel in ("gegenereerd", "gegenereerd op", "generated", "aangemaakt", "exportdatum"):
            if sleutel in self.meta:
                try:
                    return parse_datum(self.meta[sleutel])
                except ValueError:
                    return None
        return None


# ---------------------------------------------------------------- hulpfuncties

def normaliseer(s) -> str:
    return " ".join(str(s).split()).casefold()


def parse_getal(v, geheel: bool = False) -> float | None:
    """Leest 380, 380.0, '380.00', '1.234,56', '1,234.56', '€ 1.234', '0.73%'."""
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    s = re.sub(r"(?i)eur|€|\$", "", s).rstrip("%")
    if s in ("", "-", "–", "—", "n/a", "na", "N/A", "#N/A"):
        return None
    negatief = s.startswith("(") and s.endswith(")")
    if negatief:
        s = s[1:-1]
    if "." in s and "," in s:
        # het laatste scheidingsteken is de decimaal
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if geheel and re.fullmatch(r"-?\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif "." in s and re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s) and (geheel or s.count(".") > 1):
        s = s.replace(".", "")  # '13.000' impressies
    waarde = float(s)
    return -waarde if negatief else waarde


def parse_percentage(v) -> float | None:
    """Geeft een fractie terug: '0.73%' -> 0.0073."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v <= 1 else float(v) / 100  # Excel bewaart 0,73% als 0.0073
    heeft_teken = "%" in str(v)
    x = parse_getal(v)
    if x is None:
        return None
    return x / 100 if heeft_teken or x > 1 else x


def parse_datum(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and 20000 < v < 80000:  # Excel-serienummer
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip().split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"onbekende datum: {v!r}")


def _aliasmap(kolommen: dict[str, list[str]]) -> dict[str, str]:
    m: dict[str, str] = {}
    for intern, aliassen in kolommen.items():
        for a in [intern, *aliassen]:
            m[normaliseer(a)] = intern
    return m


def _herken_kop(cel, aliassen: dict[str, str]) -> str | None:
    if cel is None or str(cel).strip() == "":
        return None
    k = normaliseer(cel)
    if k in aliassen:
        return aliassen[k]
    zonder_haakjes = re.sub(r"\s*\(.*?\)\s*", " ", k).strip()   # 'spend (eur)' -> 'spend'
    return aliassen.get(zonder_haakjes)


def _lees_bladen(pad: Path) -> list[tuple[str, list[list]]]:
    ext = pad.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError as e:
            raise ExportFout("Het pakket 'openpyxl' ontbreekt. Installeer het met: pip install -r requirements.txt") from e
        wb = openpyxl.load_workbook(pad, read_only=True, data_only=True)
        try:
            return [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
        finally:
            wb.close()
    if ext in (".csv", ".txt"):
        for codering in ("utf-8-sig", "cp1252"):
            try:
                tekst = pad.read_text(encoding=codering)
                break
            except UnicodeDecodeError:
                continue
        try:
            dialect = csv.Sniffer().sniff(tekst[:5000], delimiters=";,\t")
            scheiding = dialect.delimiter
        except csv.Error:
            scheiding = ";" if tekst.count(";") > tekst.count(",") else ","
        rijen = [[c if c != "" else None for c in r] for r in csv.reader(tekst.splitlines(), delimiter=scheiding)]
        return [(pad.name, rijen)]
    if ext == ".xls":
        raise ExportFout(f"{pad.name} is een oud Excel-bestand (.xls). Sla het op als .xlsx of .csv.")
    raise ExportFout(f"{pad.name}: onbekend bestandstype. Gebruik .xlsx of .csv.")


def _zoek_koprij(rijen: list[list], aliassen: dict[str, str]):
    for i, rij in enumerate(rijen[:30]):
        gevonden: dict[str, int] = {}
        for j, cel in enumerate(rij):
            intern = _herken_kop(cel, aliassen)
            if intern and intern not in gevonden:
                gevonden[intern] = j
        if len(gevonden) >= 3:
            return i, gevonden
    return None


def _lees_meta(rijen: list[list]) -> dict[str, str]:
    meta = {}
    for rij in rijen:
        cellen = [c for c in rij if c not in (None, "")]
        if not cellen:
            continue
        eerste = str(cellen[0])
        if ":" in eerste:
            k, v = eerste.split(":", 1)
            meta[normaliseer(k)] = v.strip()
        elif len(cellen) > 1:
            meta[normaliseer(eerste)] = str(cellen[1]).strip()
    return meta


# ---------------------------------------------------------------- hoofdfunctie

def lees_export(pad: Path, cfg: KlantConfig) -> Export:
    pad = Path(pad)
    if not pad.exists():
        raise ExportFout(f"Bestand niet gevonden: {pad}")
    aliassen = _aliasmap(cfg.kolommen)

    for _blad, rijen in _lees_bladen(pad):
        gevonden = _zoek_koprij(rijen, aliassen)
        if gevonden:
            break
    else:
        voorbeeld = ", ".join(cfg.kolommen[k][0] for k in VERPLICHTE_KOLOMMEN)
        raise ExportFout(
            f"In {pad.name} staat geen herkenbare kopregel (gezocht naar kolommen als {voorbeeld}). "
            f"Is dit de goede export? Heten de kolommen anders, voeg ze dan toe onder [kolommen] "
            f"in klanten/{cfg.sleutel}.toml.")

    kop_idx, kolom = gevonden
    koprij = rijen[kop_idx]
    ontbrekend = [k for k in VERPLICHTE_KOLOMMEN if k not in kolom]
    if ontbrekend:
        koppen = ", ".join(f"'{c}'" for c in koprij if c not in (None, ""))
        raise ExportFout(
            f"In {pad.name} ontbreken de kolommen {', '.join(LABEL[k] for k in ontbrekend)}. "
            f"Gevonden kolommen: {koppen}. Heet de kolom anders, voeg die naam dan toe onder "
            f"[kolommen] in klanten/{cfg.sleutel}.toml.")

    export = Export(
        pad=pad,
        meta=_lees_meta(rijen[:kop_idx]),
        kolomkoppen={k: str(koprij[j]).strip() for k, j in kolom.items()},
        koprij=kop_idx + 1,
        rijen=[],
        ongebruikte_kolommen=[str(c).strip() for j, c in enumerate(koprij)
                              if c not in (None, "") and j not in kolom.values()],
    )

    def cel(rij, naam):
        j = kolom.get(naam)
        return rij[j] if j is not None and j < len(rij) else None

    for i in range(kop_idx + 1, len(rijen)):
        rij = rijen[i]
        regel = i + 1
        if all(c in (None, "") for c in rij):
            continue
        dim, waarde, wk = cel(rij, "dimensie"), cel(rij, "waarde"), cel(rij, "week")
        if normaliseer(dim or "") in TOTAALREGELS or normaliseer(waarde or "") in TOTAALREGELS \
                or normaliseer(wk or "") in TOTAALREGELS:
            export.meldingen.append(Melding("info", f"Totaalregel op regel {regel} overgeslagen (het script rekent zelf totalen uit).", pad.name))
            continue
        if dim in (None, "") or waarde in (None, ""):
            export.meldingen.append(Melding("controleren", f"Regel {regel} heeft geen dimensie of waarde en is overgeslagen.", pad.name))
            continue
        try:
            week = parse_datum(wk)
        except (ValueError, TypeError):
            export.meldingen.append(Melding("controleren", f"Regel {regel}: week '{wk}' is geen datum; regel overgeslagen.", pad.name))
            continue

        getallen = {}
        for m in METRIEKEN:
            ruw = cel(rij, m)
            try:
                getallen[m] = parse_getal(ruw, geheel=m in GEHELE_GETALLEN)
            except ValueError:
                getallen[m] = None
                export.meldingen.append(Melding("controleren", f"Regel {regel}: {LABEL[m].lower()} '{ruw}' is geen getal.", pad.name, week))
        try:
            ctr = parse_percentage(cel(rij, "ctr"))
        except ValueError:
            ctr = None

        export.rijen.append(Rij(week=week, dimensie=str(dim).strip(), waarde=str(waarde).strip(),
                                ctr_export=ctr, bron=pad.name, regel=regel, **getallen))

    if not export.rijen:
        raise ExportFout(f"{pad.name} bevat geen bruikbare regels onder de kopregel.")
    return export
