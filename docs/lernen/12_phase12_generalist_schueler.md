# Lerntagebuch 12 – Phase 12: Ein frischer Schüler mit mehreren Lehrern und ein schwererer Generator

Rohdaten und Regeln:
- `docs/lernen/daten/phase12_vorregistrierung.json` (alle Schwellen, vor dem ersten PPO-Schritt committet)
- `docs/lernen/daten/phase12_endvergleich.json` (gepaarter Vergleich aller Modelle)
- `docs/lernen/daten/phase12_abnahme.json` (Generator-Abnahme)
- `docs/lernen/daten/phase12_score_*.json` (Scorecards)
- `runs/phase12/state.json` (Autopilot)

*Stand 10.10. – abgeschlossen: Leon wählte B (Kandidat 44 Mio. EMA2) und gab den versiegelten Test frei.*

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
| 26 | 58,7 | 65,3 | 50,8 | 75 | 9 | 59 | 63 | 97 | 42 | 42 | 83 |
| 28 | 59,4 | 68,8 | 53,3 | 79 | 13 | 52 | 62 | 91 | 41 | 50 | 88 |
| 30 | 64,1 | 69,3 (66,0) | 50,9 (40,5) | 80 | 23 | 63 | 63 | 96 | 43 | 65 | 81 |
| 32 | 64,3 | 72,7 | 52,5 | 84 | 31 | 57 | 65 | 90 | 45 | 56 | 88 |
| 34 | 67,2 | 73,0 | 54,1 | 86 | 40 | 60 | 61 | 94 | 49 | 65 | 83 |
| 36 | 69,8 | 75,0 | 56,2 | 82 | 44 | 69 | 63 | 92 | 50 | 71 | 88 |
| 38 | 67,8 | 76,7 | 53,3 | 80 | 40 | 72 | 66 | 94 | 38 | 71 | 81 |
| 40 | 73,8 | 80,7 | 57,9 | 84 | 52 | 72 | 69 | 97 | 56 | 69 | 92 |
| 42 | 70,4 | 76,7 | 56,8 | 80 | 52 | 58 | 68 | 96 | 46 | 69 | 94 |
| 44 | 70,5 | 77,8 | 55,4 | 86 | 49 | 60 | 68 | 96 | 45 | 71 | 90 |
| 46 | 70,3 | 77,3 | 56,5 | 82 | 37 | 67 | 66 | 94 | 49 | 77 | 90 |
| 48 | 71,6 | 75,8 | 60,1 | 83 | 33 | 71 | 66 | 97 | 49 | 79 | 94 |
| 50 | 69,9 | 72,7 | 61,7 | 85 | 20 | 76 | 63 | 97 | 47 | 79 | 94 |
| 52 | 72,3 | 71,0 | – | 85 | 37 | 77 | 59 | 97 | 51 | 77 | 94 |
| 52 (EMA2) | **74,9** | 75,8 | 60,4 | 86 | 39 | 77 | 65 | 98 | 59 | 83 | 92 |

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

## Verlängerung (Leon, 9.10.)

- **Option C (6:36, 26,4 Mio.):** Entropie-Bonus 0,003 → 0,001 und neue Quelle „Prüfungs-Fähigkeiten“ (10 %).
  - Grund: Die Prüfung stand zufällig gezogen bei 15–25 %. Deterministisch war der Schüler schon bester Generalist; er spielte nur zu unsicher.
  - Wirkung: Die Prüfung stieg von 9 % (26 Mio.) auf 40–44 % (34–38 Mio.), der Generalist-Wert auf 69,8 % (36 Mio.).
- **Verlängerung (16:07, 39,5 Mio.):** Ziel 55 Mio. und 52 h; Prüfungs-Fähigkeiten 15 %; die Lernrate steigt ab 45 Mio. kurz auf 5e-5 und fällt dann auf 1e-5; das Urteilsfenster liegt bei 50/52/54 Mio.
- **Mario-Level (16:38, 40,2 Mio.):** echte Level aus dem VGLC-Korpus (Super Mario Bros., SMB 2 Japan, Super Mario Land), 10 % Anteil.
  - Der Umwandler `jumpnrun/levelgen/mario.py` repariert die Level für unsere Physik: Unser Spieler springt gut eine Kachel hoch, Mario vier. Zu hohe Hindernisse werden zu Stufen gekürzt, zu breite Abgründe verengt.
  - Vorrat: 701 Abschnitte aus 37 Leveln, 30 % davon gespiegelt. 9 ganze Level sind zurückgehalten (Messung „Mario“, nie trainiert).
  - Der Löser beweist 10 von 12 Stichproben als lösbar.
  - Ausgangswerte auf den zurückgehaltenen Leveln: P8 7/50, Schüler (38 Mio.) 11/50.
- **Schutz:** Fällt der Generalist-Wert zweimal in Folge > 3 Pp unter den Bestwert, wird der Prüfungsschwerpunkt zurückgenommen.

**Ende der Verlängerung (48–55 Mio.)**
- 22:14 (48,4 Mio.): Mario-Quelle wieder heraus. Die zurückgehaltenen Mario-Level blieben bei 20–28 von 100, ein Übertrag war nicht zu sehen. Die Phase-8-Level gingen zurück auf 30 %.
- Die Prüfung fiel in der Verlängerung von 52 % (40 Mio.) auf 20 % (50 Mio.).
  - Diagnose: Auf den Trittsteinen stürzten jetzt 36/64 Versuche ab, bei 40 Mio. waren es 17/64.
  - Wahrscheinliche Ursachen: die angehobene Lernrate und zeitweise nur 20 % Phase-8-Level.
- Dafür wuchsen Sprünge (83 %), lange Level (77 %) und Spiegel (59 %, 52 Mio. EMA2).
- Training fertig um 2:10 (55 Mio.).

**Zwei Messfehler gefunden und behoben**
- Gesicherte Kandidaten-Kopien hatten keine Einstellungsdatei. Damit liefen sie mit falscher Aktionsrate (0/64 statt 29/64). Die Kopien haben jetzt eine `.json`.
- `scorecard12`: `PPO.load` setzt den Zufallsgenerator auf den Trainings-Seed zurück, deshalb hatte `--seed` keine Wirkung. Jede Scorecard war also eine einzige, je Modell feste Stichprobe.
  - Behoben: Der Seed wird jetzt nach dem Laden gesetzt.
  - Das Endurteil nutzt die frischen Seeds 1 und 2 für alle Modelle (gepaart).

## Endurteil (gepaart, frische Seeds 1 + 2)

| Modell | Generalist | Klassisch | Prüfung | Lang | Gabeln | Kanäle | Spiegel | Sprünge | Strukturen |
|---|---|---|---|---|---|---|---|---|---|
| **Phase 12 · 44 Mio. EMA2** | **74,5** | 87 | 58 | 71 | 64 | 98 | 45 | 80 | 93 |
| Phase 12 · 52 Mio. EMA2 | 73,1 | 87 | 37 | 75 | 66 | 96 | 45 | 82 | 97 |
| Phase 12 · 40 Mio. EMA | 72,8 | 88 | 51 | 71 | 68 | 95 | 46 | 76 | 89 |
| Phase 12 · 54 Mio. EMA | 71,2 | 83 | 36 | 68 | 64 | 96 | 51 | 79 | 92 |
| Neustart (Prüfung) | 56,6 | 82 | 62 | 56 | 59 | 95 | 34 | 46 | 19 |
| Phase 11 | 55,6 | 85 | 66 | 63 | 67 | 73 | 26 | 48 | 17 |
| P8 | 40,8 | 84 | 75 | 69 | 37 | 8 | 0 | 51 | 4 |

**Kandidat: Phase 12 bei 44 Mio. (EMA2) → `models/phase12_kandidat.zip`.**
- Er liegt +18 Pp über dem besten Altmodell.
- In 7 von 8 Kategorien ist er gleichauf oder besser.
- Er hat die beste Prüfung aller Phase-12-Stände.

**Halte-Tor verfehlt:** Prüfung 58 % gegenüber P8 75 %; das Tor verlangt ≥ P8 − 5 Pp. Leon entscheidet: Tor streng (kein Kandidat) oder Kandidat mit offen ausgewiesener Prüfungs-Lücke.

**Lehren**
- Der größte Hebel war, dass der Schüler zu unsicher spielte: Der deterministische Generalist lag 15 Pp über dem zufällig gezogenen. Ein kleinerer Entropie-Bonus und eine fallende Lernrate halfen mehr als jede neue Quelle.
- Echte Mario-Level ließen sich umwandeln, verbesserten aber nichts messbar. Unsere Physik (1 Kachel Sprunghöhe) macht sie nach der Reparatur zu Abgrund-Präzisionsprüfungen ohne Übertrag.
- Eine Verlängerung mit wieder angehobener Lernrate kostet Präzision. Die Prüfung reagiert darauf als Erstes.

## Leons Entscheidung und der versiegelte Test (10.10.)

- **Entscheidung B:** Der 44-Mio.-Stand (EMA2) wird Kandidat, die Prüfungs-Lücke wird offen ausgewiesen. P8 bleibt als Prüfungs-Spezialist erhalten.
- **Versiegelter Test:** einmalig gespielt (`scripts/versiegelt12.py`), gepaart (gleicher Seed), zufällig gezogen, nur Gruppensummen.

| Modell | exam2 (geheime 2. Prüfung) | handmade8 versiegelt | handmade9 versiegelt | **gesamt** (95 %-Intervall) |
|---|---|---|---|---|
| **Phase 12** | **107/128 (84 %)** | 119/128 (93 %) | **62/128 (48 %)** | **288/384 = 75,0 %** (70–79 %) |
| P8 | 89/128 (70 %) | 119/128 (93 %) | 32/128 (25 %) | 240/384 = 62,5 % (58–67 %) |
| Phase 11 | 58/128 (45 %) | 123/128 (96 %) | 48/128 (38 %) | 229/384 = 59,6 % (55–64 %) |
| Neustart | 32/128 (25 %) | 123/128 (96 %) | 31/128 (24 %) | 186/384 = 48,4 % (43–53 %) |

**Phase 12 ist auf den nie gesehenen Leveln klar am besten.** Die Intervalle überlappen sich nicht mit P8. Auf der geheimen zweiten Prüfung schlägt Phase 12 sogar P8 (84 % zu 70 %), obwohl P8 die offene Prüfung besser kann. Die Prüfungs-Lücke ist also eher eine Spezialisierung von P8 auf genau dieses eine Level als eine echte Schwäche des Generalisten.

## Diagnose des Kandidaten (zufällig vs. deterministisch, Seed 1)

Werkzeug: `jumpnrun/rl/diagnose12.py`. Bild: `medien/phase12/diagnose_endstand.png`. Daten: `daten/phase12_diagnose/`.

| Kategorie | zufällig | determ. | häufigste Ursache der Niederlagen | unsichere Schritte |
|---|---|---|---|---|
| Klassisch rechts | 86 | 88 | Abgrund 55 % | 2 % |
| Prüfung | 57 | 100* | Abgrund 57 % | **7 %** (P8 1 %) |
| Lange Level | 74 | 80 | Gegner 57 % | 2 % |
| Gabeln/Sackgassen | 62 | **83** | **hängen geblieben 77 %** | 3 % |
| Kanäle | 97 | 92 | Gegner | 1 % |
| Links/Spiegel | **43** | **50** | **Abgrund 70 %** | 7 % |
| Schwere Sprünge | 77 | 79 | Abgrund 82 % | 2 % |
| Neue Strukturen | 94 | 92 | hängen geblieben 67 % | 3 % |

\* deterministisch ist die Prüfung ein einziger fester Ablauf.

Generalist-Wert zufällig/deterministisch: Phase 12 73,7/82,9; Neustart 55,3/65,0; Phase 11 57,1/57,1; P8 41,1/45,7.

**Befunde**
1. **Prüfung und Gabeln: kein Können-, sondern ein Sicherheitsproblem.**
   - Deterministisch löst der Bot beide deutlich besser (+43 bzw. +21 Pp).
   - Auf der Prüfung ist er in 7 % der Schritte unsicher, P8 nur in 1 %.
   - In Gabeln führt das zufällige Ziehen dazu, dass er in Sackgassen herumirrt (77 % der Niederlagen: hängen geblieben).
2. **Links/Spiegel: ein echtes Können-Problem.** Auch deterministisch schafft der Bot nur 50 %, und 70 % der Niederlagen sind Stürze. Präzise Sprünge nach links sitzen noch nicht.
3. **Schwere Sprünge und Klassisch** scheitern fast nur an Abgründen. Das ist die Präzisionsgrenze.
4. **Lange Level** scheitern vor allem an Gegnern (57 %).

## Geschärfte Wahl beim Spielen (Temperatur)

Gleiche Level, Seed 1. Die Wahrscheinlichkeiten werden beim Spielen geschärft: p^(1/T), neu normiert. T = 1 ist das Netz wie trainiert. Bild: `medien/phase12/temperatur.png`.

| Temperatur | Phase 12 Generalist | Phase 12 Prüfung | P8 Generalist | P8 Prüfung |
|---|---|---|---|---|
| 1,0 | 73,7 | 57 | 41,1 | 77 |
| 0,7 | 79,1 | 80 | 43,5 | 91 |
| 0,5 | 82,3 | 90 | 45,0 | 95 |
| **0,3** | **84,7** | **98** | 45,1 | 98 |
| 0 (determ.) | 82,9 | (ein Ablauf) | 45,7 | (ein Ablauf) |

**Befunde**
- Bei T = 0,3 schließt sich die Prüfungs-Lücke vollständig (98 % gegenüber 98 % bei P8, je 256 Versuche).
- Bei T = 0,3 steigt der Generalist-Wert auf 84,7 %, mehr als ganz deterministisch: Ein Rest Zufall hilft gegen das Festfahren.
- Die Schwäche von Phase 12 war also zum großen Teil zu unsicheres Spielen, nicht fehlendes Können.
- **Echte Lücke bleibt Links/Spiegel (52 %).** Dort hilft Schärfen kaum.
