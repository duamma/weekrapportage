#!/usr/bin/env python3
"""Maak de weekrapportage van een klant.

    python3 maak_rapport.py                      # enige/standaard klant, laatste week
    python3 maak_rapport.py --klant zerocopter   # kies een klant
    python3 maak_rapport.py --week 2026-10-27    # rapport over een eerdere week
    python3 maak_rapport.py --export ~/Downloads/export.xlsx   # extra bestand buiten de exportmap
    python3 maak_rapport.py --open               # open het rapport daarna in de browser

Zie README.md.
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

from weekrapport.analyse import analyseer          # noqa: E402
from weekrapport.config import ConfigFout, klanten_in, laad_klant  # noqa: E402
from weekrapport.inlezen import ExportFout, lees_export  # noqa: E402
from weekrapport.opschonen import schoon_op        # noqa: E402
from weekrapport.rapport import schrijf            # noqa: E402

EXTENSIES = {".xlsx", ".xlsm", ".csv"}


def vind_exports(map_: Path) -> list[Path]:
    if not map_.exists():
        return []
    return sorted(p for p in map_.iterdir()
                  if p.suffix.lower() in EXTENSIES and not p.name.startswith(("~$", ".")))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Maak een weekrapportage van campagne-exports.")
    p.add_argument("--klant", help="naam van het configuratiebestand in klanten/ (zonder .toml)")
    p.add_argument("--week", help="startdatum van de week (JJJJ-MM-DD); standaard de laatste week in de data")
    p.add_argument("--export", nargs="+", default=[], metavar="BESTAND", help="extra exportbestand(en)")
    p.add_argument("--open", action="store_true", help="open het HTML-rapport na afloop")
    args = p.parse_args(argv)

    klanten = klanten_in(PROJECT / "klanten")
    klant = args.klant or (klanten[0] if len(klanten) == 1 else None)
    if not klant:
        print(f"Kies een klant met --klant. Beschikbaar: {', '.join(klanten) or 'geen (maak er een in klanten/)'}")
        return 2

    try:
        cfg = laad_klant(klant, PROJECT)
        bestanden = vind_exports(cfg.exportmap) + [Path(x).expanduser() for x in args.export]
        if not bestanden:
            raise ExportFout(f"Geen exports gevonden in {cfg.exportmap}. Zet de export (.xlsx of .csv) in die map.")
        print(f"{cfg.naam}: {len(bestanden)} export(s) inlezen...")
        exports = [lees_export(b, cfg) for b in bestanden]
        data = schoon_op(exports, cfg)
        week = date.fromisoformat(args.week) if args.week else None
        analyse = analyseer(data, cfg, week)
        paden = schrijf(analyse, data, cfg)
    except (ConfigFout, ExportFout) as e:
        print(f"\nFOUT: {e}")
        return 1
    except ValueError as e:
        print(f"\nFOUT: {e}")
        return 1

    n_contr = sum(1 for m in data.meldingen if m.niveau == "controleren")
    n_corr = sum(1 for m in data.meldingen if m.niveau == "gecorrigeerd")
    print(f"Week van {analyse.week:%d-%m-%Y}: {n_corr} automatische correctie(s), {n_contr} punt(en) om te controleren.\n")
    print("In het kort:")
    for k in analyse.kort:
        print("  - " + k.replace("**", ""))
    print("\nWat ik zou doen:")
    for i, x in enumerate(analyse.acties, 1):
        print(f"  {i}. " + x.replace("**", ""))
    print("\nRapport:   ", paden["html"].relative_to(PROJECT))
    print("Markdown:  ", paden["markdown"].relative_to(PROJECT))
    print("Schone data:", paden["data"].relative_to(PROJECT))
    if args.open:
        webbrowser.open(paden["html"].resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
