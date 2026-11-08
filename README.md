# Weekrapportage campagnes

Dit script maakt van een campagne-export (Excel of CSV) een weekrapport met drie onderdelen:

1. **Wat veranderde:** de cijfers van deze week naast vorige week en naast het gemiddelde van de weken daarvoor, plus hoe het budget is verschoven.
2. **Wat aandacht vraagt:** segmenten die geld kosten zonder genoeg op te leveren, grote schommelingen, en wat juist goed werkt.
3. **Wat ik zou doen:** maximaal vijf concrete adviezen.

## Opgeleverd

| Wat | Waar |
|---|---|
| De workflow (code) | `maak_rapport.py` en de map `weekrapport/` |
| Output week 4: interactief rapport | [`rapporten/zerocopter/2026-11-03_weekrapport.html`](rapporten/zerocopter/2026-11-03_weekrapport.html). Download het en open het in je browser |
| Output week 4: PDF | [`rapporten/zerocopter/2026-11-03_weekrapport.pdf`](rapporten/zerocopter/2026-11-03_weekrapport.pdf) |
| Output week 4: tekst | [`rapporten/zerocopter/2026-11-03_weekrapport.md`](rapporten/zerocopter/2026-11-03_weekrapport.md). Deze kun je direct op GitHub lezen |
| Opgeschoonde data, week 1-4 | `rapporten/zerocopter/schone_data.csv` |
| Wat ik met meer tijd zou toevoegen | [onderaan deze README](#wat-ik-met-meer-tijd-zou-toevoegen) |

Het HTML-rapport volgt de huisstijl uit het presentatietemplate: Inter Tight en Source Serif 4, petrol, mint en crème. Bovenaan staan KPI-kaarten en een grafiek per week. De tabellen zijn sorteerbaar en met de knop **Opslaan als PDF** maak je een A4-versie. Is Playwright voor Python geïnstalleerd, dan maakt het script die PDF ook zelf.

---

## Elke week: zo maak je het rapport

1. Download de export uit de advertentietool. Gebruik hetzelfde rapport als altijd: *Demografie per week (alle campagnes)*.
2. Zet het bestand in de map **`exports/zerocopter/`**. De bestandsnaam maakt niet uit en oude exports laat je gewoon staan.
3. Maak het rapport op een van deze manieren:
   - **Mac:** dubbelklik op `Maak rapport (Mac).command`.
   - **Windows:** dubbelklik op `Maak rapport (Windows).bat`.
   - **Terminal:**
     ```bash
     python3 maak_rapport.py --open
     ```
4. Het rapport opent in je browser. Je vindt het ook in `rapporten/zerocopter/`.
5. Lees eerst **Datakwaliteit → Controleren** onderaan het rapport. Staat daar iets, kijk er dan naar voordat je het rapport deelt. Staat er niets, dan is de data in orde.

Je kunt het script zo vaak draaien als je wilt. Het leest elke keer alle exports in de map opnieuw in, dus er is geen verborgen opgeslagen toestand die kapot kan gaan.

### Handige varianten

```bash
python3 maak_rapport.py --week 2026-10-27
```
Maakt opnieuw het rapport over een eerdere week. De datum is de startdatum van die week.

```bash
python3 maak_rapport.py --export ~/Downloads/export.xlsx
```
Gebruikt een export die niet in de exportmap staat.

```bash
python3 maak_rapport.py --klant zerocopter
```
Kiest de klant. Dit is pas nodig als er meer dan één klant is.

---

## Eenmalig installeren

Je hebt **Python 3.11 of nieuwer** nodig.

- **Mac:** typ `python3 --version` in Terminal. Is de versie te oud of krijg je een foutmelding, installeer Python dan via [python.org](https://www.python.org/downloads/).
- **Windows:** installeer Python via [python.org](https://www.python.org/downloads/) en vink tijdens de installatie *Add python.exe to PATH* aan.

Open daarna een terminal in deze map en installeer het enige extra pakket, `openpyxl` (voor het lezen van Excel):

```bash
python3 -m pip install -r requirements.txt
```

Op Windows typ je `py` in plaats van `python3`.

Wil je controleren of alles werkt? Draai dan de tests:

```bash
python3 -m unittest discover tests
```

---

## Wat het script doet

```
exports/<klant>/*.xlsx|csv
   │ 1. inlezen     zoekt zelf de kopregel en herkent kolommen aan hun naam, niet aan hun positie
   │ 2. opschonen   dubbele regels, schrijfwijzen, ontbrekende waarden, CTR-controle, totalen per dimensie
   │ 3. analyse     week op week, budgetverschuiving, signalen per segment volgens vaste regels
   ▼ 4. rapport     HTML + Markdown + schone_data.csv in rapporten/<klant>/
```

| Bestand | Rol |
|---|---|
| `maak_rapport.py` | Startpunt: de opdracht die je draait |
| `klanten/<klant>.toml` | Alles wat per klant verschilt: kolomnamen, labels, KPI en drempels |
| `weekrapport/inlezen.py` | Leest één export in en zet de kolommen om naar vaste interne namen |
| `weekrapport/opschonen.py` | Voegt exports samen en voert de controles en correcties uit |
| `weekrapport/analyse.py` | Berekent de cijfers en past de regels toe die tot signalen en adviezen leiden |
| `weekrapport/rapport.py` | Schrijft het rapport (Markdown en CSV) |
| `weekrapport/html_rapport.py` | Schrijft het HTML-rapport en de PDF. De kleuren en fonts staan bovenaan in `HUISSTIJL` |

### Tegen een andere opbouw van de export bestand

De export van week 4 is anders opgebouwd dan die van week 1-3. Het script vangt dat automatisch op en zet de verschillen in het rapport:

| Verschil | Hoe het script ermee omgaat |
|---|---|
| Extra regel `Gegenereerd: …` bovenaan, waardoor de kopregel een regel lager staat | Het zoekt de kopregel zelf op in de eerste 30 regels |
| `Week (startdatum)` heet nu `Week`, `Uitgaven (EUR)` heet nu `Spend (EUR)` | Kolommen worden herkend via de lijst namen in `[kolommen]`, en een toevoeging tussen haakjes wordt genegeerd |
| Nieuwe dimensie *Senioriteit* | Wordt meegenomen en als "nieuw deze week" gemarkeerd, zonder vergelijking met vorige week |
| `Informatietechnologie` heet nu `IT`, en `1000+` heet `1.000+` | Worden samengevoegd via `[labels]`. Andere varianten die alleen verschillen in hoofdletters, spaties of punten voegt het script zelf samen |
| Bedragen staan deels als tekst (`"380.00"`) en deels als getal | Beide notaties worden gelezen, net als `1.234,56` en `€ 690` |

Daarnaast vond het script deze fouten in de export van week 1-3 en corrigeerde ze:

- een dubbele regel (Security / Risk in week 2);
- een ontbrekend aantal conversies (Overig in week 2). Dat is afgeleid uit het totaal van de dimensie Bedrijfsgrootte;
- een onjuiste CTR (Onderwijs in week 1: 6,80% in plaats van 0,68%). Het script rekent de CTR daarom altijd zelf uit.

**Belangrijk voor wie met de cijfers werkt:** Functie, Bedrijfsgrootte en Senioriteit zijn elk een opdeling van dezelfde campagnes. Binnen één dimensie tellen de segmenten op tot het totaal. Tel je ze over dimensies heen op, dan tel je alles twee of drie keer. Het script gebruikt juist dat gegeven om te controleren of er een regel mist of dubbel staat.

Lukt het niet om de export te lezen, bijvoorbeeld omdat een verplichte kolom een onbekende naam heeft, dan stopt het script met een melding die zegt wat er mis is en waar je het oplost. Het maakt dan geen half rapport.

### Hoe de adviezen tot stand komen

Het script gebruikt vaste, controleerbare regels en geen AI. Dezelfde data geeft dus altijd hetzelfde rapport. De regels:

| Signaal | Regel (standaarddrempel) | Advies |
|---|---|---|
| Groot verschil in budget | Totale uitgaven veranderen ≥ 25% ten opzichte van vorige week | Zoek uit of dat bewust was |
| Geld zonder resultaat | Segment kost deze week ≥ €100 en levert 0 leads op | Sluit uit of verlaag het bod |
| Structureel duur | Kosten per lead over de hele periode ≥ 1,3× het gemiddelde (vanaf €300 aan uitgaven) | Verlaag het budget |
| Leads zonder conversie | ≥ 3 weken en ≥ €300 aan uitgaven zonder één websiteconversie | Kosten per lead normaal: vraag sales naar de kwaliteit van de leads. Duur: verlaag het budget |
| Kans | Kosten per lead ≤ 0,7× het gemiddelde, met minstens 3 leads deze week | Geef stap voor stap meer budget |

Per segment zijn de aantallen klein: vaak minder dan 10 leads per week. Daarom gelden minimumbedragen en kijken de regels waar mogelijk naar de hele periode in plaats van naar één week. Je past de drempels aan onder `[drempels]` in het klantbestand.

---

## Een tweede klant toevoegen

Wat per klant verschilt, staat in één configuratiebestand. De code hoef je niet aan te passen zolang de export van de nieuwe klant dezelfde vorm heeft: één regel per week, per dimensie en per segment, met impressies, klikken, uitgaven en leads. Kolomnamen, taal, scheidingsteken, getalnotatie en het aantal regels boven de kopregel mogen anders zijn.

**Stap 1: maak een klantbestand.** Kopieer `klanten/zerocopter.toml` naar bijvoorbeeld `klanten/acme.toml`. De bestandsnaam wordt de naam die je gebruikt in `--klant acme`. Pas daarin aan:

```toml
[klant]
naam = "Acme"                 # naam in de titel van het rapport
account = "Acme BV"           # precies zoals op de regel "Account: …" in hun export
exportmap = "exports/acme"
rapportmap = "rapporten/acme"

[kpi]
primair = "leads"             # of "conversies" als deze klant stuurt op websiteconversies
```

**Stap 2: controleer de kolomnamen.** Open een export van de nieuwe klant. Staat een kolomnaam niet in de lijst onder `[kolommen]`, voeg hem dan toe. Een voorbeeld: hun export heet de klikken "Link clicks".

```toml
klikken = ["Klikken", "Clicks", "Link clicks"]
```

Zet onder `[labels.<Dimensie>]` de segmenten die in hun exports verschillend geschreven worden. Gebruiken ze andere namen voor dimensies, bijvoorbeeld "Job function", zet die dan onder `[dimensies]`.

**Stap 3: zet de exports neer** in `exports/acme/`.

**Stap 4: draai het rapport.**

```bash
python3 maak_rapport.py --klant acme --open
```

Als het niet lukt, zegt de foutmelding welke kolom ontbreekt en in welk bestand je hem toevoegt.

**Stap 5 (optioneel): pas de drempels aan.** Heeft de klant een veel groter of kleiner budget, pas dan `min_uitgaven_week` en `min_uitgaven_periode` aan onder `[drempels]`. Voor een klant met €10.000 per week is €100 zonder resultaat geen signaal.

**Stap 6 (optioneel): maak een startbestand.** Wil je ook voor deze klant iets om op te dubbelklikken, kopieer dan het startbestand en verander `--open` in `--klant acme --open`.

**Twee beveiligingen:**

- Elke klant heeft een eigen exportmap. Daarnaast weigert het script een export waarvan de regel `Account:` niet bij de klant past. Een export die in de verkeerde map belandt, komt dus niet in het verkeerde rapport terecht.
- De test `TestTweedeKlant` in `tests/test_weekrapport.py` doet precies dit voor een verzonnen klant: een CSV-bestand met puntkomma's, Engelse kolomnamen en Nederlandse getallen. Je kunt hem als voorbeeld gebruiken.

**Als de export echt anders van vorm is**, bijvoorbeeld één regel per campagne in plaats van per segment, of uit Google Ads in plaats van LinkedIn, dan is alleen een extra inleesfunctie nodig in `weekrapport/inlezen.py`. Die zet de export om naar dezelfde interne regels: week, dimensie, waarde en de cijfers. Het opschonen, de analyse en het rapport werken daarna ongewijzigd. Een campagne behandel je dan als dimensie "Campagne".

---

## Problemen oplossen

| Melding | Oplossing |
|---|---|
| `Geen exports gevonden in …` | Zet de export in `exports/<klant>/` |
| `In … ontbreken de kolommen …` | Voeg de nieuwe kolomnaam toe onder `[kolommen]` in het klantbestand |
| `… is een export van account 'X', niet van 'Y'` | Het bestand staat in de verkeerde klantmap |
| `… is een oud Excel-bestand (.xls)` | Sla het op als .xlsx of .csv |
| `ModuleNotFoundError: openpyxl` / `Het pakket 'openpyxl' ontbreekt` | Voer `python3 -m pip install -r requirements.txt` uit |
| `tomllib` niet gevonden | Je Python is ouder dan 3.11; installeer een nieuwere versie |
| Een week staat in twee exports | Het script gebruikt de nieuwste export en zet dat onder Datakwaliteit |
| Onder *Controleren* staat dat de export is gemaakt voordat de week voorbij was | Download de export opnieuw na afloop van de week en draai het rapport nog een keer |

---

## Wat ik met meer tijd zou toevoegen

Deze lijst is gesorteerd op wat volgens mij de meeste waarde toevoegt.

**Betere adviezen**
1. **Een samenvatting in gewone taal door een LLM, bovenop de vaste regels.** De regels bepalen *wat* er gezegd wordt: het blijven controleerbare cijfers. Claude schrijft daar een korte toelichting bij voor de klant en mag daarbij alleen getallen gebruiken die het script heeft uitgerekend. Een check vergelijkt elk getal in de tekst met de data, zodat er geen verzonnen cijfers in komen.
2. **Leadkwaliteit uit het CRM erbij halen.** Op dit moment kan het script alleen zeggen dat het de kwaliteit van leads niet weet. Met data uit HubSpot of Salesforce (welke leads werden een afspraak of een deal) wordt "kosten per lead" ook "kosten per goede lead". Het advies "vraag sales" verdwijnt dan.
3. **Statistiek voor kleine aantallen.** Nu gelden er vaste minimumbedragen. Betrouwbaarheidsintervallen (bijvoorbeeld een Bayesiaanse schatting van de kosten per lead per segment) maken duidelijker hoe zeker elk signaal is.
4. **Doelen per klant.** Een streefwaarde voor de kosten per lead en een maandbudget in de config, zodat het rapport ook zegt "op koers voor de maand: ja of nee".
5. **Combinaties van dimensies**, zoals Functie × Bedrijfsgrootte, als de advertentietool die kan exporteren.

**Minder handwerk**
6. **De export automatisch ophalen** via de API van LinkedIn Ads of Google Ads, in plaats van downloaden en in een map zetten.
7. **Een geplande run en verzending:** elke maandag om 9:00 via GitHub Actions of een cron-job, met het rapport naar Slack of de mail van de klant. Het script is daar al geschikt voor, want het draait zonder vragen en zonder opgeslagen toestand.
8. **Een wizard voor een nieuwe klant:** `maak_rapport.py --nieuwe-klant` leest een voorbeeldexport en stelt de kolomnamen en labels voor de config zelf voor.
9. **Een webformulier voor wie geen terminal gebruikt:** export erin slepen, rapport eruit. Te bouwen met Streamlit of als interne webpagina.

**Robuuster**
10. **Exports van meer platforms.** Een extra inleesfunctie per bron (Google Ads, Meta, één regel per campagne), die alles omzet naar hetzelfde interne formaat.
11. **Een plek voor historie.** Een kleine database of een Google Sheet in plaats van een map met exports, zodat meerdere collega's dezelfde historie gebruiken.
12. **Meer tests met afwijkende exports:** lege weken, valuta's, Engelstalige exports, kolommen in een andere volgorde.
13. **Klantspecifieke huisstijl:** kleuren en logo per klant in de config, voor rapporten die rechtstreeks naar de klant gaan.
