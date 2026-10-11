# Lerntagebuch 13 – Phase 13: Links-Präzision und Nachschärfen

Rohdaten und Regeln:
- `docs/lernen/daten/phase13_vorregistrierung.json` (Regeln und Stand 0)
- `daten/phase13_stand0.json`
- `runs/phase13/state.json` (Autopilot)

*Stand 11.10. – abgeschlossen.*

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

Start-Hürde: Beim ersten Start war der Speicher mit demos12 und demos13 zusammen zu klein; der Prozess wurde bei 13 GB beendet. Seitdem läuft BC2 mit demos13 statt demos12.

Messungen je 1 Mio. (T = 0,3, Seed 7; EMA, dazu EMA2 alle 3 Mio.):

| Stand | Generalist T0,3 | T1 | ohne Links | Klassisch | Prüfung | Lang | Gabeln | Kanäle | Links | Sprünge | Strukturen | Links-Sprünge | spiegelweg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Stand 0 | 83.7 | 73.8 | 88.1 | 92 | 96 | 77 | 77 | 95 | 52 | 88 | 92 | 1/24 | 0/16 |
| +1 | 86.6 | 73.3 | 90.4 | 89 | 95 | 76 | 89 | 94 | 60 | 92 | 98 | 0/24 | 2/16 |
| +1 (EMA2) | 84.7 | 71.5 | 89.1 | 95 | 95 | 81 | 80 | 96 | 54 | 85 | 92 | 1/24 | 1/16 |
| +2 | 87.5 | 75.4 | 91.6 | 93 | 97 | 80 | 89 | 96 | 59 | 94 | 92 | 1/24 | 6/16 |
| +3 | 86.3 | 75.9 | 91.1 | 90 | 98 | 77 | 88 | 95 | 53 | 96 | 94 | 1/24 | 5/16 |
| +4 | 85.6 | 75.4 | 90.2 | 93 | 98 | 73 | 85 | 93 | 53 | 94 | 96 | 1/24 | 6/16 |
| +4 (EMA2) | 88.6 | 76.3 | 93.3 | 94 | 99 | 80 | 91 | 95 | 56 | 96 | 98 | 0/24 | 6/16 |
| +5 | 86.1 | 74.9 | 88.9 | 89 | 93 | 84 | 79 | 93 | 66 | 92 | 92 | 1/24 | 10/16 |
| +6 | 84.0 | 76.2 | 87.5 | 90 | 96 | 78 | 74 | 95 | 60 | 90 | 90 | 1/24 | 7/16 |
| +7 | 84.9 | 73.7 | 86.2 | 89 | 93 | 73 | 71 | 94 | 75 | 94 | 90 | 1/24 | 11/16 |
| +7 (EMA2) | 86.0 | 75.5 | 88.2 | 92 | 92 | 80 | 72 | 95 | 70 | 96 | 90 | 1/24 | 8/16 |
| +8 | 85.8 | 74.7 | 87.7 | 91 | 97 | 77 | 71 | 92 | 72 | 96 | 90 | 1/24 | 12/16 |
| +9 | 86.9 | 75.4 | 89.3 | 91 | 94 | 86 | 69 | 94 | 70 | 98 | 94 | 1/24 | 9/16 |
| +10 | 85.9 | 78.0 | 87.7 | 91 | 99 | 82 | 70 | 88 | 73 | 90 | 94 | 2/24 | 13/16 |
| +10 (EMA2) | 87.5 | 73.1 | 88.9 | 89 | 96 | 79 | 72 | 96 | 78 | 94 | 96 | 1/24 | 13/16 |
| +11 | 84.3 | 76.8 | 85.9 | 90 | 98 | 81 | 64 | 86 | 73 | 88 | 96 | 2/24 | 13/16 |
| +12 | 84.4 | 74.6 | 85.6 | 88 | 95 | 79 | 63 | 84 | 76 | 94 | 96 | 1/24 | 12/16 |
| +13 | 85.1 | 78.1 | 85.9 | 90 | 94 | 86 | 62 | 83 | 79 | 92 | 94 | 2/24 | 12/16 |
| +13 (EMA2) | 84.6 | 75.3 | 85.6 | 94 | 93 | 78 | 64 | 88 | 77 | 88 | 94 | 2/24 | 13/16 |
| +14 | 83.1 | 73.5 | 84.4 | 89 | 93 | 80 | 62 | 86 | 74 | 88 | 94 | 4/24 | 12/16 |

**Entscheidungspunkte:**
- E1 (2 Mio.) erreicht, E2 (5 Mio.) erreicht (Links/Spiegel 66 %).
- Die Schutzregel griff nie. Nur bei +14 Mio. lag „ohne Links“ einmal unter der Grenze.

**Beobachtung:**
- Bei +1 bis +4 Mio. stieg alles, auch die Gabeln. Die Dev-Level gabel_drei und kreuzung, die noch nie ein Modell sicher geschafft hatte, gelangen bei +2 Mio. erstmals.
- Danach tauschte das Links-Training Gabel-Können gegen Links-Können: spiegelweg stieg von 0/16 bis 13/16, gabel_drei und kreuzung fielen wieder auf 0.

## Urteil (gepaart, frische Seeds 1 + 2)

Daten: `daten/phase13_urteil.json`, Bild: `medien/phase13/urteil.png`.

| Stand | Generalist T0,3 | T1 | Links/Spiegel | Gabeln | spiegelweg | gabel_drei | kreuzung |
|---|---|---|---|---|---|---|---|
| Stand 0 (Phase-12-Kandidat) | 84,0 | 74,5 | 49 | 78 | 0/32 | 8/24 | 0/24 |
| **+2 Mio. (Kandidat)** | **87,0** | 75,2 | 52 | **90** | 4/32 | **21/24** | **18/24** |
| +4 Mio. EMA2 | 86,8 | 74,7 | 54 | 87 | 5/32 | 23/24 | 13/24 |
| +5 Mio. | 83,6 | 74,9 | 58 | 73 | 15/32 | 17/24 | 0/24 |
| +9 Mio. | 86,3 | 74,0 | 67 | 70 | 17/32 | 1/24 | 0/24 |
| +10 Mio. | 87,2 | 76,6 | 77 | 69 | 30/32 | 0/24 | 0/24 |
| +10 Mio. EMA2 (Links-Alternative) | 87,0 | 75,6 | 70 | 73 | 27/32 | 0/24 | 0/24 |
| +15 Mio. (Ende) | 86,6 | 77,0 | 75 | 63 | 27/32 | 1/24 | 0/24 |

**Ergebnis nach der vorregistrierten Regel:**
- Regel: bester Generalist bei T = 0,3, keine Kategorie mehr als 5 Pp unter Stand 0.
- Kandidat: **+2 Mio.** (`models/phase13_kandidat.zip`) mit 87,0 % (+3 Pp über Stand 0), ohne Einbuße in irgendeiner Kategorie, mit Gabeln 90 % und erstmals gabel_drei und kreuzung.
- +10 Mio. (87,2 %) scheidet aus (Gabeln −8 Pp).
- Die Links-Alternative +10 Mio. EMA2 liegt gleichauf (86,98 %), mit Links/Spiegel 70 % und spiegelweg 27/32, aber ohne gabel_drei und kreuzung. Sie bleibt als `models/phase13_links_alternative.zip` erhalten.

**Lehren**
- Das Nachschärfen (niedrige Lernrate, kleiner Entropie-Bonus) bringt den Gewinn in den ersten 2 Mio. Schritten.
- Links lässt sich lernen: spiegelweg geht von 0 auf 84 %, sobald die richtigen Level (gespiegelte schwere Sprünge und Trittsteine) und Demos da sind. Die schwersten gespiegelten Sprungketten bleiben aber bei < 10 %.
- Mit einem Netz dieser Größe konkurrieren Links-Präzision und Gabel-Entscheidungen um dieselbe Kapazität bzw. Gewichtung. Beides gleichzeitig hielt kein Stand.
- Der versiegelte Test ist verbraucht und wurde nicht erneut gespielt.
