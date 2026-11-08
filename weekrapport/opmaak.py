"""Getallen en datums in Nederlandse notatie."""
from __future__ import annotations

from datetime import date, timedelta

MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]
MIN = "−"  # echt minteken


def _nl(s: str) -> str:
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def eur(x: float | None, dec: int | None = 2) -> str:
    """€1.265,75. Met dec=None: zonder centen als het een rond bedrag is."""
    if x is None:
        return "–"
    if dec is None:
        dec = 0 if abs(x - round(x)) < 0.005 else 2
    teken = MIN if x < 0 else ""
    return f"{teken}€{_nl(f'{abs(x):,.{dec}f}')}"


def getal(x: float | None) -> str:
    """Aantal; een gemiddelde krijgt 1 decimaal onder de 100, anders afgerond."""
    if x is None:
        return "–"
    if abs(x - round(x)) < 1e-9 or abs(x) >= 100:
        return _nl(f"{x:,.0f}")
    return _nl(f"{x:,.1f}")


def pct(fractie: float | None, dec: int = 2) -> str:
    """0.0075 -> '0,75%'."""
    if fractie is None:
        return "–"
    return _nl(f"{fractie * 100 + 1e-9:.{dec}f}") + "%"   # 0,625% -> 0,63% (afronden zoals Excel)


def verandering(nu: float | None, vorig: float | None) -> float | None:
    if nu is None or vorig in (None, 0):
        return None
    return (nu - vorig) / vorig


def pct_verschil(d: float | None) -> str:
    """Relatieve verandering: '+12%', '−45%', '0%'."""
    if d is None:
        return "–"
    r = round(d * 100)
    if r == 0:
        return "0%"
    return f"{'+' if r > 0 else MIN}{abs(r)}%"


def pp(d: float) -> str:
    """Verschil in procentpunt: '+18 pp'."""
    r = round(d * 100)
    return f"{'+' if r > 0 else MIN if r < 0 else '±'}{abs(r)} pp"


def factor(x: float) -> str:
    return _nl(f"{x:.1f}") + "×"


def datum(d: date) -> str:
    return f"{d.day} {MAANDEN[d.month - 1]} {d.year}"


def week_kort(d: date) -> str:
    return f"week van {d.day} {MAANDEN[d.month - 1][:3]}"


def weekperiode(start: date) -> str:
    """'3 t/m 9 november 2026' of '27 oktober t/m 2 november 2026'."""
    eind = start + timedelta(days=6)
    if start.month == eind.month:
        return f"{start.day} t/m {eind.day} {MAANDEN[eind.month - 1]} {eind.year}"
    if start.year == eind.year:
        return f"{start.day} {MAANDEN[start.month - 1]} t/m {eind.day} {MAANDEN[eind.month - 1]} {eind.year}"
    return f"{datum(start)} t/m {datum(eind)}"


def opsomming(items: list[str]) -> str:
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " en " + items[-1]
