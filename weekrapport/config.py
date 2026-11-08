"""Klantconfiguratie inlezen uit klanten/<klant>.toml."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

VERPLICHTE_KOLOMMEN = ("week", "dimensie", "waarde", "impressies", "klikken", "spend", "leads")
OPTIONELE_KOLOMMEN = ("ctr", "conversies")

STANDAARD_DREMPELS = {
    "grote_verandering_pct": 25,
    "kpi_verandering_pct": 20,
    "min_uitgaven_week": 100,
    "min_uitgaven_periode": 300,
    "min_weken_zonder_conversie": 3,
    "min_leads_winnaar": 3,
    "factor_duur": 1.3,
    "factor_goedkoop": 0.7,
    "factor_kwaliteitscheck": 1.1,
    "verschuiving_pp": 10,
    "ctr_tolerantie_pp": 0.05,
    "max_acties": 5,
}


class ConfigFout(Exception):
    """Fout in een klantconfiguratie."""


@dataclass
class KlantConfig:
    sleutel: str                      # bestandsnaam zonder .toml, bv. "zerocopter"
    naam: str                         # weergavenaam, bv. "ZeroCopter"
    account: str | None               # verwachte accountnaam in de export
    exportmap: Path
    rapportmap: Path
    primaire_kpi: str                 # "leads" of "conversies"
    kolommen: dict[str, list[str]]    # interne naam -> kolomnamen in exports
    dimensies: dict[str, str]         # alias -> vaste dimensienaam
    labels: dict[str, dict[str, str]] # dimensie -> {label in export: label in rapport}
    drempels: dict[str, float]


def klanten_in(map_: Path) -> list[str]:
    """Alle klanten waarvoor een configuratie bestaat."""
    return sorted(p.stem for p in Path(map_).glob("*.toml") if not p.stem.startswith("_"))


def laad_klant(sleutel: str, projectmap: Path) -> KlantConfig:
    projectmap = Path(projectmap)
    pad = projectmap / "klanten" / f"{sleutel}.toml"
    if not pad.exists():
        bekend = ", ".join(klanten_in(projectmap / "klanten")) or "geen"
        raise ConfigFout(f"Geen configuratie gevonden voor klant '{sleutel}' ({pad}). Bekende klanten: {bekend}.")
    try:
        with pad.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigFout(f"{pad.name} is geen geldig TOML-bestand: {e}") from e

    klant = data.get("klant", {})
    kolommen = {k: [str(a) for a in (v if isinstance(v, list) else [v])] for k, v in data.get("kolommen", {}).items()}
    ontbreekt = [k for k in VERPLICHTE_KOLOMMEN if not kolommen.get(k)]
    if ontbreekt:
        raise ConfigFout(f"In {pad.name} ontbreken onder [kolommen]: {', '.join(ontbreekt)}.")
    onbekend = set(kolommen) - set(VERPLICHTE_KOLOMMEN) - set(OPTIONELE_KOLOMMEN)
    if onbekend:
        raise ConfigFout(f"Onbekende kolomnaam(en) onder [kolommen] in {pad.name}: {', '.join(sorted(onbekend))}.")

    kpi = data.get("kpi", {}).get("primair", "leads")
    if kpi not in ("leads", "conversies"):
        raise ConfigFout(f"[kpi] primair moet \"leads\" of \"conversies\" zijn, niet \"{kpi}\".")
    if kpi == "conversies" and not kolommen.get("conversies"):
        raise ConfigFout("[kpi] primair = \"conversies\", maar er staat geen 'conversies' onder [kolommen].")

    eigen_drempels = data.get("drempels", {})
    onbekend = set(eigen_drempels) - set(STANDAARD_DREMPELS)
    if onbekend:
        raise ConfigFout(f"Onbekende drempel(s) in {pad.name}: {', '.join(sorted(onbekend))}. "
                         f"Toegestaan: {', '.join(STANDAARD_DREMPELS)}.")

    return KlantConfig(
        sleutel=sleutel,
        naam=klant.get("naam", sleutel),
        account=klant.get("account") or None,
        exportmap=projectmap / klant.get("exportmap", f"exports/{sleutel}"),
        rapportmap=projectmap / klant.get("rapportmap", f"rapporten/{sleutel}"),
        primaire_kpi=kpi,
        kolommen=kolommen,
        dimensies={str(k): str(v) for k, v in data.get("dimensies", {}).items()},
        labels={str(d): {str(k): str(v) for k, v in m.items()} for d, m in data.get("labels", {}).items()},
        drempels={**STANDAARD_DREMPELS, **eigen_drempels},
    )
