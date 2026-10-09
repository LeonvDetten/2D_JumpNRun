# Lerntagebuch 12 – Phase 12: Ein frischer Schüler mit mehreren Lehrern und ein schwererer Generator

Rohdaten und Regeln:
- `docs/lernen/daten/phase12_vorregistrierung.json` (alle Schwellen, vor dem ersten PPO-Schritt committet)
- `docs/lernen/daten/phase12_endvergleich.json` (gepaarter Vergleich aller Modelle)
- `docs/lernen/daten/phase12_abnahme.json` (Generator-Abnahme)
- `docs/lernen/daten/phase12_score_*.json` (Scorecards)
- `runs/phase12/state.json` (Autopilot)

*Entwurf – wird während der Phase ergänzt.*

## Ausgangslage: der gepaarte Endvergleich (8.10.)

Verglichen wurden alle Modelle auf den erlaubten Gruppen, mit neuen Seeds und zusätzlich 128 Prüfungsversuchen. **Kein Modell ist überall das beste.**
- **P8** führt bei der Prüfung (197/256), auf dem handmade8-Test (94/128) und auf langen Leveln.
- **Phase 11** führt bei Sackgassen und alten Dev-Leveln.
- **Der Neustart** führt bei den Phase-9-Fähigkeiten (Kanäle) und beim Spiegeln.

Zwei Befunde erklärten das Plateau:
1. **Der Generator war ausgereizt.** Auf frischen Leveln aller Stufen gewannen alle Modelle 83–100 %, auf Handleveln deutlich weniger. Das Training lieferte kaum noch Lernsignal.
2. **Drei Dev-Level hat kein Modell je gewonnen** (gabel_drei, kreuzung, spiegelweg). Solche Strukturen kamen im Training nicht vor.

**Leons Entscheidungen:**
- frisches Netz als Schüler,
- schwerer Generator mit schweren Sprüngen, neuen Strukturen und langen Leveln,
- Budget ~48 h,
- einfache Scorecard und frühe Entscheidungspunkte.

## Die Scorecard

8 Kategorien, jede gemessen auf festen, erlaubten Leveln, dazu der **Generalist-Wert** als Mittel der 8 (`jumpnrun/rl/scorecard12.py`).

Ausgangslage (Seed 0):

| | P8 | Phase-10-Lehrer | Phase 11 | Neustart |
|---|---|---|---|---|
| 1 Klassisch rechts | 84 | 84 | **89** | 85 |
| 2 Prüfung | **74** | 64 | 63 | 57 |
| 3 Lange Level | **67** | 65 | 60 | 63 |
| 4 Gabeln/Sackgassen | 42 | 58 | **66** | 61 |
| 5 Kanäle/Umkehren | 8 | 90 | 72 | **91** |
| 6 Links/Spiegel | 0 | 11 | 32 | **35** |
| 7 Schwere Sprünge | 50 | 50 | 52 | 52 |
| 8 Neue Strukturen | 4 | 12 | 19 | **23** |
| **Generalist-Wert** | 41,0 | 54,4 | 56,6 | **58,3** |

## Generator v11 und Abnahme (E0)

`jumpnrun/levelgen/hard.py` hat 15 Bausteine:
- **Neu:** präzise Sprungketten (die weitesten Sprünge je Höhenstufe, auch die „engen“, die nur von bestimmten Positionen klappen), Landungen bei Gegnern, Ketten mit herabfallenden Gegnern, Dreifach-Gabel, Umweg, Kreuzung.
- **Die schwersten alten Bausteine:** Sprung-Katalog, Decke, Schacht, Rampe, Klettern, zwei Wege, Köder-Gabel, Kanal, Graben.

Familien: Sprünge, Strukturen, gemischt, lang (550–900 Kacheln).

Dazu kommt ein neuer Löser `solve_path_legs`: abschnittsweise entlang der Distanzkarte, damit lange und verwinkelte Level beweisbar werden.

**Lehre:**
- Die erste Fassung der Sprünge war zu leicht; P8 schaffte 90 %.
- Nach dem Nachschärfen (10–18 Sprünge je Kette, enge Sprünge, mehr Gegner) liegen alle drei Altmodelle bei 44 %.
- Der Preis: Der Löser beweist nur noch 63 % der Sprung-Level.
- Leons Entscheidung: Die Hälfte der schweren Trainingslevel kommt aus einem vom Löser bewiesenen Pool.

| Kriterium | Ergebnis |
|---|---|
| Vielfalt | 15 Bausteine, keiner über 11 %, 193 verschiedene Paare in Folge, breiteres Wegprofil als v9/v10 ✔ |
| Schwierigkeit (Altmodelle) | Sprünge 44 %, Strukturen 6–23 %, gemischt 15–19 %, lang 0–6 % ✔ |
| Abstand zu Mess-Leveln | keine Kopie ✔ |
| Lösbar (Löser) | Proben alle bewiesen; Sprünge 63 %, Strukturen 89 %, gemischt 84 %, lang 47 % der erzeugten Level ⚠ |

Leon gab den Generator am 8.10. frei („mit Löser-Pool“).

## Mehrere Lehrer

**Zuordnung** (`scripts/lehrer_profil12.py`): Je Leveltyp wird der Lehrer gewählt, der auf frischen Validierungsleveln am meisten gewinnt. Vorrang hat P8, außer ein anderer ist ≥ 5 Pp besser. Ergebnis:
- P8 für klassische und lange Level,
- Phase 11 für Sackgassen,
- Phase-10-Lehrer und Neustart für Kanäle,
- Neustart für Truhe-links und kurze gespiegelte Level,
- kein Lehrer für schwere gespiegelte und v11-Level.

**Weitere Regeln:**
- P8 lehrt nie auf Leveln mit Gabel- oder Kanal-Bausteinen.
- Das Gewicht der Lehrer fällt von 1 auf 0 über 20 Mio. Schritte.

## Verlauf

**Vorbereitung und Start**
- **Löser-Demos v11:** 613 bewiesene schwere Level. Sie dienen als Demos und zugleich als Pool für die Hälfte der schweren Trainingslevel.
- **BC-Start:**
  - 16 000 Schritte auf 600k Phase-8-Beispielen und 1,1 Mio. weiteren (davon 12 700 links+springen).
  - Bester Stand: Holdout 0,985 (ohne „rechts“ 0,970), P(links+springen) auf links+springen-Zuständen 0,98, auf alten Zuständen 0,0013, Validierung 30,6 %.
- **Start des Trainings:** 8.10. um 10:53 auf den Kernen 0–2.
  - Tempo: ~440 fps mit 5 Lehrern, ab Stufe 10 ~300–340 fps.
  - Die Messung läuft auf Kern 3.

| Mio. | Generalist | dev_alt (Neustart) | F (Neustart) | Klassisch | Prüfung | Lang | Gabeln | Kanäle | Links/Spiegel | Sprünge | Strukturen |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 16,5 | 22,2 (17,1) | 35,6 (26,5) | 12 | 0 | 1 | 32 | 56 | 16 | 0 | 15 |
| 2 | 22,1 | 30,7 (36,4) | 34,8 (29,8) | 22 | 0 | 8 | 34 | 76 | 22 | 0 | 15 |
| 4 | 30,5 | 48,9 (47,0) | 38,1 (32,2) | 34 | 0 | 14 | 42 | 91 | 25 | 2 | 35 |
| 6 | 35,8 | 55,4 (49,7) | 37,8 (38,3) | 47 | 4 | 30 | 50 | 87 | 22 | 15 | 31 |
| 8 | 39,2 | 55,4 (51,9) | 46,8 (42,7) | 57 | 19 | 29 | 45 | 82 | 25 | 8 | 48 |
| 10 | 41,7 | 59,1 (53,3) | 42,6 (39,5) | 57 | 19 | 29 | 52 | 86 | 23 | 19 | 48 |
| 12 | 51,1 | 56,2 (57,1) | 48,3 (39,4) | 63 | 30 | 41 | 56 | 93 | 38 | 31 | 56 |
| 14 | 49,3 | 60,8 (≈59) | 47,9 | 67 | 21 | 44 | 58 | 96 | 22 | 23 | 62 |
| 16 | 51,2 | 65,1 (61,8) | 49,2 (44,3) | 68 | 25 | 33 | 59 | 99 | 36 | 29 | 60 |
| 18 | 49,7 | 67,3 | 48,8 | 70 | 16 | 55 | 58 | 88 | 34 | 12 | 65 |
| 20 | 53,4 | 61,4 | 52,9 | 71 | 24 | 55 | 54 | 91 | 37 | 29 | 67 |
| 22 | 56,1 | 65,9 | 46,7 | 74 | 22 | 56 | 58 | 93 | 33 | 38 | 75 |
| 24 | 56,5 | 68,8 | 49,2 | 83 | 15 | 51 | 59 | 88 | 39 | 40 | 77 |

**Entscheidungspunkte**
- **E1 (2 Mio.): formal verfehlt.**
  - dev_alt lag unter der Neustart-Kurve.
  - Erklärbar durch den Mischplan: 35 % Phase-8-Level gegenüber 60 % beim Neustart.
  - Das Training lief vorregistriert weiter.
- **E2 (6 Mio.): erreicht.**
  - dev_alt liegt 5,7 Pp über dem Neustart, F gleichauf.
  - Sprünge und Strukturen steigen.
  - Die neuen Strukturen liegen ab 4 Mio. über dem bisher besten Modell.

**Leons Eingriffe**
- **19:40 (10,5 Mio.): gespiegelte lange Level heraus.**
  - Im Training gewann der Schüler kurze gespiegelte Level zu 13–20 %, gespiegelte lange zu 0 % (Fortschritt 10 %). Diese lieferten kaum Lernsignal.
  - Ihr Anteil geht seitdem an kurze gespiegelte Level.
  - Nachher: kurze gespiegelte Level im Training 19 % gewonnen und 40 % Fortschritt (vorher 13 % und 30 %).
  - In der Scorecard stieg Links/Spiegel bei 12 Mio. von 23 auf 38 %. Das liegt erstmals über dem bisher besten Modell. Ein Teil davon kann auch von der höheren Curriculum-Stufe kommen.
- **19:45: kein automatischer Stopp mehr an E3/E4.**
  - Leons Vorgabe: Das Training läuft ohne Unterbrechung.
  - Fragen sind erlaubt; ohne Antwort wird nach bestem Gewissen weitergemacht.
  - Verfehlte Punkte werden nur noch notiert und berichtet.

**12 Mio.: der größte Sprung bisher**
- Der Generalist-Wert steigt von 41,7 auf 51,1 %, alle 8 Kategorien legen zu.
- Neue Strukturen liegen bei 56 %, mehr als doppelt so viel wie jedes Altmodell.
- Offen bleiben:
  - Klassisch rechts (63 % gegen 89 %),
  - die Prüfung (30 % gegen 74 % bei P8),
  - dev_alt, das leicht unter die Neustart-Kurve fällt, während die Lehrer ausklingen.

**14 Mio.: der Sprung bei 12 Mio. war zum Teil Glück**
- Links/Spiegel fällt von 38 auf 22 %, Prüfung von 30 auf 21 %, Sprünge von 31 auf 23 %.
- Kategorie 6 beruht auf nur 52 Versuchen. Die gespiegelten Validierungslevel standen bei 7/12 und jetzt bei 2/12.
- Im Training sind die kurzen gespiegelten Level seit 12 Mio. flach bei 22 %. Spiegeln ist der Engpass.
- Alte und strukturelle Fähigkeiten wachsen weiter: Klassisch 67 %, dev_alt 61 % (wieder über der Neustart-Kurve), Strukturen 62 %.

**Spiegel-Diagnose (22:50)**
- Die gespiegelten Level kommen gleichverteilt aus den Stufen 4–12, unabhängig vom Können.
- Seit 12 Mio. gewonnen: Stufen 4–6 50–67 %, Stufe 7 32 %, Stufen 8–9 5–9 %, Stufen 10–12 0–2 %. Die Hälfte liefert also kaum Lernsignal.
- Häufigste Todesursache: Sturz in die Grube (45 %).
- Vorbereitet, aber noch nicht aktiv: ein eigenes Curriculum für gespiegelte Level (`--mirror-adaptive`). Es spielt bis zur Stufe, die gespiegelt zu ≥ 50 % gewonnen wird, plus die nächste; 10 % kommen aus allen Stufen.

**E3 (16 Mio.): formal verfehlt, Training läuft weiter (Leons Vorgabe)**
- dev_alt 65,1 % (Ziel ≥ 55 %, Neustart-Kurve 61,8 %) und F 49,2 % (Neustart 44,3 %) liegen klar über dem Neustart.
- Aber nur 3 von 8 Kategorien liegen über dem fertigen Neustart-Modell (Ziel 5): Kanäle, Links/Spiegel, Strukturen.
- Seit 12 Mio. pendelt der Generalist-Wert zwischen 49 und 51 %. Prüfung, lange Level und Sprünge schwanken stark (Rauschen ±5 Pp), ein Fortschritt ist dort nicht erkennbar.

**18–20 Mio.: ein Tief und die Erholung**
- Bei 18 Mio. fielen die Prüfung auf 16 % (Fortschritt 54 → 41 %, 256 Versuche) und die Sprünge auf 6/48. Das Lehrer-Gewicht lag da nur noch bei 0,1.
- Bei 20 Mio. kamen beide zurück: Prüfung 24 %, Sprünge 14/48. Der Generalist-Wert erreichte mit 53,4 % einen neuen Bestwert, Klassisch rechts 71 %.
- Im Training stiegen die kurzen gespiegelten Level ab 18 Mio. von 22 auf 33 % gewonnen, ohne weiteren Eingriff.
- Ab 20 Mio. sind die Lehrer ganz aus.
