# Der Bot

[← zurück zur README](../README.md)

Der Bot hat Space Pirate per **Reinforcement Learning** gelernt, also durch Ausprobieren mit Belohnung. Das
Verfahren ist PPO (*Proximal Policy Optimization*) aus stable-baselines3. Niemand hat ihm gesagt, wie man über eine
Lücke springt oder einen Gegner stompt. Er bekommt nur ein Signal: weiter auf dem Weg zur Kiste ist gut, eine Grube
ist schlecht, die Kiste ist sehr gut.

Das repräsentative Modell ist **`models/space_pirate_bot.zip`** (Phase 13, Stand 11.10.2026). Seine Kennzahlen
stehen in `models/space_pirate_bot.json`.

![Der Bot auf dem Prüfungslevel 2023](medien/bot_pruefung_2023.gif)

*Das Original-Level von 2023 im Zeitraffer. [Ganzer Lauf in Echtzeit (MP4)](medien/bot_pruefung_2023.mp4)*

## Was der Bot sieht und tut

| Baustein | Beschreibung |
|---|---|
| **Sicht** (`grid`) | 13 × 33 Kacheln um den Spieler (13 nach hinten, 19 nach vorn), 4 Ebenen: Blöcke, Kisten, Gegner mit Laufrichtung, Spieler |
| **Übersichtskarte** (`overview`) | grobe Karte, je 4 Kacheln zu einer Spalte zusammengefasst, 40 Spalten: Wo kann man stehen, wo liegt die Kiste? |
| **Zahlen** (`vec`) | 23 Werte: Fallgeschwindigkeit, am Boden, Blickrichtung, Nachladezeit, Position in der Kachel, nächste Gegner, Zeit, … |
| **Aktionen** | 7: nichts, links, rechts, springen, rechts+springen, schießen, links+springen; eine Entscheidung alle 2 Frames (≈ 15 pro Sekunde) |
| **Netz** | kleine Faltungsnetze (CNN) für Sicht und Karte, ein MLP für die Zahlen, zusammen etwa 1 Mio. Parameter (`jumpnrun/rl/policy.py`) |
| **Belohnung** | +0,1 je Kachel Fortschritt auf dem Weg zur Kiste, −1 beim Tod, +2 an der Kiste (`jumpnrun/rl/env.py`) |
| **Spielweise** | Die Aktionswahrscheinlichkeiten werden geschärft (Temperatur 0,3). Bei Temperatur 1 macht der Bot öfter einzelne ungenaue Sprünge. |

Der Bot spielt **dieselbe Simulation** wie ein Mensch (`jumpnrun/core/`). Sie ist deterministisch und ohne Grafik,
deshalb lässt sie sich etwa 19.000 Frames pro Sekunde und CPU-Kern simulieren.

## Wie gut ist er?

Gemessen auf Leveln, auf denen er **nie trainiert** hat: Prüfung, Test-Serie und frische Generator-Seeds.

| Messung | Ergebnis |
|---|---|
| Prüfungslevel 2023 (256 Versuche, Temperatur 0,3) | 98 % |
| Generalist-Wert: 8 Kategorien, gepaart, frische Seeds | 87,0 % |
| Klassisch rechts / schwere Sprünge / neue Strukturen | 93 % / 93 % / 95 % |
| Gabeln und Sackgassen / Kanäle / lange Level | 90 % / 95 % / 82 % |
| Links / gespiegelte Level (die größte offene Lücke) | 52 % |

Quelle: Phase-13-Urteil im [Lerntagebuch](lernen/13_phase13_links.md). Zum Vergleich: P8
(`models/phase8_final.zip`) kommt beim Generalist-Wert auf 45 %.

### Lernfortschritt auf dem Prüfungslevel

![Erfolgsquote je Lernstand](medien/lernkurve.png)

Jeder gespeicherte Lernstand hat das Prüfungslevel am 12.10.2026 je 64 Mal gespielt, einmal mit Temperatur 1
(das Netz, wie es trainiert wurde) und einmal mit 0,3 (geschärft). Messwerte:
[`medien/pruefung_messung.json`](medien/pruefung_messung.json), Skript: `scripts/make_readme_media.py measure`.
Was man sieht:

- **Phase 1–5:** Diese Lernstände kommen über die ersten Abschnitte nicht hinaus (0 %).
- **Phase 6 und 7:** Sie gewinnen nur mit der ungeschärften Spielweise (27 % bzw. 72 %). Geschärft bleiben sie
  hängen: Die zufällige Aktionswahl rettet sie aus Stellen, an denen sie sich nicht sicher sind.
- **Ab Phase 8:** Die geschärfte Spielweise ist nahezu fehlerfrei (94–100 %).
- **Phase 13:** Der aktuelle Bot erreicht hier 60 von 64 Versuchen. Die maßgebliche Messung mit 256 Versuchen ergab
  98 %; bei 64 Versuchen schwankt der Wert um einige Prozentpunkte.

Dass Phase 12 und 13 bei Temperatur 1 schwächer sind als P8, ist bekannt. Diese Netze sind breiter trainiert, auf
viele Levelarten statt vor allem auf rechts-laufende Level, und spielen ungeschärft unsicherer
([Phase 12](lernen/12_phase12_generalist_schueler.md)).

![Lernfortschritt als Video](medien/bot_lernfortschritt.gif)

*Je ein Clip pro Lernstand, 16 Bots gleichzeitig. [MP4](medien/bot_lernfortschritt.mp4)*

## Zuschauen

```
python -m jumpnrun.rl.watch --level levels/exam/level.txt --live              # Geister-Ansicht im Fenster
python -m jumpnrun.rl.watch --level levels/exam/level.txt --video pruefung.mp4 # als Video
python -m jumpnrun.rl.watch --model models/phase8_final.zip --level levels/test_serie/berg.txt --live
python spacepirate.py                                                          # „Gegen den Bot“ in der App
```

![32 Bots gleichzeitig](medien/geister_32.gif)

## Die Modelle in `models/`

| Datei | Lernstand |
|---|---|
| `space_pirate_bot.zip` | **aktueller Bot** (Phase 13, = `phase13_kandidat.zip`) |
| `phase13_links_alternative.zip` | Phase-13-Alternative mit mehr Links-Training |
| `phase12_kandidat.zip`, `phase11_kandidat.zip`, `phase10_kandidat_*.zip` | Generalist-Linie |
| `neustart_kandidat_*.zip` | frisch trainiertes Netz, siehe [Tagebuch 10b](lernen/10b_neustart.md) |
| `phase8_final.zip` | ehrlich gemessener Stand der ersten Linie |
| `phase7_final.zip`, `phase6_*.zip`, `phase5*.zip`, `phase1–3.zip` | frühe Phasen |

Zu jedem Modell gehört eine `.json` mit Entscheidungstakt (`action_repeat`), Beobachtungsform und Herkunft.
Geladen wird es mit `jumpnrun.rl.modelinfo.load_model` (läuft unter jeder Python-Version, siehe `load_ppo`).

Wie der Bot dahin kam (13 Phasen, Fehlschläge eingeschlossen), steht im [Lerntagebuch](lernen/00_ueberblick.md).
Trainingsbefehle: [training.md](training.md).
