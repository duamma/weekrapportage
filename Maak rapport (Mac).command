#!/bin/bash
# Dubbelklik om het weekrapport te maken. Het rapport opent daarna in je browser.
cd "$(dirname "$0")"
python3 maak_rapport.py --open
echo
read -p "Klaar. Druk op Enter om dit venster te sluiten."
