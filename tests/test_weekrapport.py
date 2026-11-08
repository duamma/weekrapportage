"""Tests: python3 -m unittest discover tests"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from weekrapport.analyse import analyseer  # noqa: E402
from weekrapport.config import laad_klant  # noqa: E402
from weekrapport.inlezen import ExportFout, lees_export, parse_getal, parse_percentage  # noqa: E402
from weekrapport.opschonen import schoon_op  # noqa: E402
from weekrapport.rapport import maak_markdown  # noqa: E402

EXPORTS = PROJECT / "exports" / "zerocopter"


def zerocopter():
    cfg = laad_klant("zerocopter", PROJECT)
    exports = [lees_export(p, cfg) for p in sorted(EXPORTS.glob("*.xlsx"))]
    return cfg, schoon_op(exports, cfg)


class TestGetallen(unittest.TestCase):
    def test_notaties(self):
        self.assertEqual(parse_getal("380.00"), 380.0)
        self.assertEqual(parse_getal(155.75), 155.75)
        self.assertEqual(parse_getal("1.265,75"), 1265.75)
        self.assertEqual(parse_getal("1,265.75"), 1265.75)
        self.assertEqual(parse_getal("€ 690"), 690.0)
        self.assertEqual(parse_getal("13.000", geheel=True), 13000.0)
        self.assertIsNone(parse_getal(None))
        self.assertIsNone(parse_getal(""))

    def test_percentage(self):
        self.assertAlmostEqual(parse_percentage("0.73%"), 0.0073)
        self.assertAlmostEqual(parse_percentage("0,73%"), 0.0073)
        self.assertAlmostEqual(parse_percentage(0.0073), 0.0073)


class TestZeroCopter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.data = zerocopter()

    def test_beide_opbouwen_gelezen(self):
        self.assertEqual(sorted(self.data.weekbron), [date(2026, 10, 13), date(2026, 10, 20), date(2026, 10, 27), date(2026, 11, 3)])
        wk4 = [r for r in self.data.rijen if r.week == date(2026, 11, 3)]
        self.assertEqual(len(wk4), 13)
        self.assertAlmostEqual(sum(r.spend for r in wk4 if r.dimensie == "Functie"), 690.0)

    def test_dubbele_regel_weg(self):
        sec = [r for r in self.data.rijen if r.week == date(2026, 10, 20) and r.waarde == "Security / Risk"]
        self.assertEqual(len(sec), 1)

    def test_labels_gelijkgetrokken(self):
        functies = {r.waarde for r in self.data.rijen if r.dimensie == "Functie"}
        groottes = {r.waarde for r in self.data.rijen if r.dimensie == "Bedrijfsgrootte"}
        self.assertNotIn("Informatietechnologie", functies)
        self.assertEqual(groottes, {"1-49", "50-249", "250-999", "1.000+"})

    def test_ontbrekende_waarde_afgeleid(self):
        overig = next(r for r in self.data.rijen if r.week == date(2026, 10, 20) and r.waarde == "Overig")
        self.assertEqual(overig.conversies, 0)

    def test_foute_ctr_gemeld(self):
        self.assertTrue(any("6,80%" in m.tekst for m in self.data.meldingen))

    def test_totalen_kloppen(self):
        self.assertFalse([m for m in self.data.meldingen if m.niveau == "controleren"])

    def test_analyse_week4(self):
        a = analyseer(self.data, self.cfg)
        self.assertEqual(a.week, date(2026, 11, 3))
        self.assertAlmostEqual(a.totaal.spend, 690.0)          # niet dubbel geteld over dimensies
        self.assertAlmostEqual(a.totaal_vorig.spend, 1265.75)
        self.assertEqual(a.totaal.leads, 12)
        self.assertEqual(a.nieuwe_dimensies, ["Senioriteit"])
        cat = {s.waarde: s.categorie for segs in a.segmenten.values() for s in segs}
        self.assertEqual(cat["Entry / Senior"], "uitsluiten")
        self.assertEqual(cat["Security / Risk"], "opschalen")
        self.assertEqual(cat["Overig"], "afschalen")
        self.assertEqual(cat["Consultancy"], "kwaliteit")
        self.assertIn("Totaal budget", [p.onderwerp for p in a.aandacht])
        md = maak_markdown(a, self.data, self.cfg, __import__("datetime").datetime(2026, 11, 10, 9, 0))
        for kop in ("## Wat veranderde", "## Wat aandacht vraagt", "## Wat ik zou doen", "## Datakwaliteit"):
            self.assertIn(kop, md)


class TestTweedeKlant(unittest.TestCase):
    """Een andere klant met een csv-export, andere kolomnamen en Nederlandse getallen."""

    def setUp(self):
        self.map = Path(tempfile.mkdtemp())
        (self.map / "klanten").mkdir()
        (self.map / "exports" / "acme").mkdir(parents=True)
        tekst = (PROJECT / "klanten" / "zerocopter.toml").read_text(encoding="utf-8")
        tekst = tekst.replace('naam = "ZeroCopter"', 'naam = "Acme"').replace('account = "ZeroCopter"', 'account = "Acme BV"')
        tekst = tekst.replace('exportmap = "exports/zerocopter"', 'exportmap = "exports/acme"')
        tekst = tekst.replace('rapportmap = "rapporten/zerocopter"', 'rapportmap = "rapporten/acme"')
        tekst = tekst.replace('klikken    = ["Klikken", "Clicks"]', 'klikken    = ["Klikken", "Clicks", "Link clicks"]')
        (self.map / "klanten" / "acme.toml").write_text(tekst, encoding="utf-8")
        rijen = ["Account: Acme BV", "",
                 "Weekstart;Dimension;Segment;Impressions;Link clicks;Kosten;Leads;Conversions",
                 "06-10-2026;Job function;Marketing;10.000;80;1.200,00;10;2",
                 "06-10-2026;Job function;Sales;5.000;40;600,00;2;0",
                 "13-10-2026;Job function;Marketing;12.000;90;1.300,00;12;3",
                 "13-10-2026;Job function;Sales;4.000;30;500,00;0;0"]
        (self.map / "exports" / "acme" / "export.csv").write_text("\n".join(rijen), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.map)

    def test_csv_met_andere_kolommen(self):
        cfg = laad_klant("acme", self.map)
        e = lees_export(self.map / "exports" / "acme" / "export.csv", cfg)
        data = schoon_op([e], cfg)
        a = analyseer(data, cfg)
        self.assertAlmostEqual(a.totaal.spend, 1800.0)
        self.assertEqual(a.dimensies, ["Functie"])
        sales = next(s for s in a.segmenten["Functie"] if s.waarde == "Sales")
        self.assertEqual(sales.categorie, "uitsluiten")

    def test_export_van_verkeerde_klant_geweigerd(self):
        cfg = laad_klant("acme", self.map)
        e = lees_export(EXPORTS / "Campagne_export_week_4.xlsx", cfg)
        with self.assertRaises(ExportFout):
            schoon_op([e], cfg)


if __name__ == "__main__":
    unittest.main()
