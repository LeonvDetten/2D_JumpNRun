# Lerntagebuch 13 – Phase 13: Links-Präzision und Nachschärfen

Rohdaten und Regeln:
- `docs/lernen/daten/phase13_vorregistrierung.json` (Regeln und Stand 0)
- `daten/phase13_stand0.json`
- `runs/phase13/state.json` (Autopilot)

*Entwurf – wird während der Phase ergänzt.*

## Ausgangslage (10.10.)

Phase-12-Kandidat (44 Mio. EMA2), gemessen mit Seed 7 als Stand 0:

| Messung | Ergebnis |
|---|---|
| Generalist T = 0,3 | 83,7 % |
| Generalist T = 1 | 73,8 % |
| ohne Links-Kategorie (T = 0,3) | 88,1 % |
| Links/Spiegel | 52 % |
| Schwere Sprünge (nach rechts) | 88 % |
| **dieselben Sprung-Proben gespiegelt** | **1 von 24** |
| spiegelweg | 0 von 16 |

Der Bot kann schwere Sprungketten nach rechts, nach links praktisch gar nicht.

**Warum das Spiegeln bisher wenig brachte**
- Die Spiegel-Quelle spiegelte nur zufällige v9-Level. Die eine Hälfte war unlösbar, die andere leicht.
- Schwere Sprungketten kamen gespiegelt nie vor.
- Links-Demos mit präzisen Sprüngen gab es nicht.
- Das Spiel ist symmetrisch, wenn die Gegner mitgespiegelt werden: Alle gespiegelten Löser-Demos gewinnen beim Nachspielen.

**Leons Entscheidungen**
- 15 Mio. Schritte (~15 h), Start vom Kandidaten.
- 30 % links: 20 % neue Links-Quelle, 10 % adaptiv gespiegelt.
- Niedrige Lernrate. Der Generalist bleibt das Hauptziel; ein früherer Stand darf gewinnen.

## Bau

- **`jumpnrun/levelgen/links.py`:** neue Quelle mit drei Familien, alle gespiegelt, halb mit nach links laufenden Gegnern.
  - Links-Sprünge: v11-Sprungfamilien, halb aus dem Löser-Pool.
  - Links-Trittsteine: Variante „Prüfungs-Fähigkeiten“ mit adaptiver Stufe.
  - Links-lang.
- **`scripts/demos13.py`:** 610 der 613 Löser-Demos von demos12 gespiegelt; Aktionen links↔rechts, Gegner nach links, beim Nachspielen bestätigt. Dazu 5 frische Demos. Zusammen 21 338 Schritte mit links+springen.
- **`milestones13`:** jede 1 Mio. die Scorecard bei T = 1 und T = 0,3, dazu Links-Sprünge (gespiegelte Proben, nie trainiert) und spiegelweg.
- **`autopilot13`:** Schutzregeln, E1/E2 automatisch (Leon ist ~15 h nicht da).
- **Probelauf** (53k Schritte): Neue Links-Level werden zu 15 % gewonnen. Dort gibt es also viel Lernsignal.

Start: 10.10. um 15:43.

## Verlauf
