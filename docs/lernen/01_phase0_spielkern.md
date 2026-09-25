# Lerntagebuch 1 – Phase 0: Ein Spiel, das man trainieren kann

Bevor ein Bot etwas lernen kann, muss das Spiel drei Dinge erfüllen:

1. **Deterministisch:** gleiche Eingaben ⇒ exakt gleicher Spielverlauf. Sonst kann der Bot nicht
   herausfinden, *welche* Aktion zu Erfolg oder Misserfolg geführt hat.
2. **Schnell ohne Bildschirm:** Der Bot braucht Millionen Schritte. Mit 30 Bildern pro Sekunde „in Echtzeit“
   wären das Wochen.
3. **Faire Regeln:** Jede Situation muss lösbar sein, Fehler müssen bestraft werden (Grube = Tod), und
   es darf keine Tricks geben, die das Spiel aushebeln.

## Was im alten Spielcode (2023) nicht gepasst hat

| Problem | Folge für RL | Lösung |
|---|---|---|
| Kein Tod in Gruben – man fiel ewig | Bot lernt nie, dass Gruben schlecht sind | Tod, sobald der Spieler unter den Levelrand fällt |
| Sprung 55 px hoch, Block 60 px | Stufen nur per Kollisions-Trick; Wände hochklettern möglich | saubere Kollision, Sprung 78 px (> 1 Block, < 2 Blöcke) |
| Zeit über die echte Uhr (`get_ticks`) | Regeln hängen von der Rechengeschwindigkeit ab | alles in Frames gezählt (z. B. Schuss-Abklingzeit = 30 Frames) |
| Chunk-Zählung verrutscht (20 vs. 21 Kacheln) | ab Kachel ~440 fällt man durch den Boden, Gegner frieren ein | Kollision direkt über ein Kachelraster, keine Chunks mehr |
| Tod = `sys.exit()` | Programm beendet sich, statt eine neue Episode zu starten | Status `died_enemy` / `died_pit` / `won` |
| Grafik und Logik vermischt | kein schnelles Training ohne Fenster | Simulation (`jumpnrun/core`) komplett getrennt von Grafik (`jumpnrun/render`) |

Die neue Simulation schafft **~19.000 Frames pro Sekunde auf einem CPU-Kern**, das Spiel läuft mit 30.
Ein Kern simuliert also etwa 10 Minuten Spielzeit pro Sekunde.

## Die neue Physik in Zahlen

- Laufen: 8 px pro Frame · Schwerkraft: +1 px/Frame² · Sprung: Startgeschwindigkeit −12
- Sprunghöhe: 12 + 11 + … + 1 = **78 px** (ein Block = 60 px), Flugzeit **24 Frames**
- Sprungweite: 24 × 8 = **192 px ≈ 3,2 Blöcke** → Lücken bis 2 Blöcke sind sicher, 3 Blöcke erfordern Präzision
- Gegner: 5 px/Frame, drehen an Wänden um, laufen über Kanten (und fallen dann in Gruben).
  Sie starten erst, wenn sie ins Bild kommen – wie bei Mario.
- Gegner besiegen: **draufspringen** (nur wenn man von oben kommt) oder **abschießen** (1 Schuss pro Sekunde)

Mensch (`game.py`) und Bot spielen **exakt dieselbe Simulation** – nur die Eingabe kommt einmal von der
Tastatur und einmal vom neuronalen Netz.

## Der Löser: Ist ein Level überhaupt schaffbar?

`jumpnrun/levelgen/solver.py` durchsucht die echte Simulation nach einem Weg zur Truhe (A*-Suche:
„bisher verbrauchte Zeit + geschätzte Restzeit“). Er benutzt **dieselben 6 Aktionen wie der Bot** –
„lösbar“ heißt also immer „lösbar für den Bot“.

Das war wichtig, denn: **Dein Original-Level war mit sauberer Physik nicht schaffbar.** Gleich am Anfang
(Kachel 30 → 33) musste man zwei Blockreihen auf einmal hoch – das ging früher nur mit dem Kletter-Trick.
Mit dem Erreichbarkeits-Werkzeug (`--map`) sieht man das sofort:

```
python -m jumpnrun.levelgen.solver levels/exam/level.txt --map
```

markiert jede Stelle, auf der man stehen kann, mit `*`. Ergebnis: Mit **einem einzigen zusätzlichen Block**
(Kachel 31, Reihe 6) ist der ganze obere Weg wieder erreichbar. Sonst ist dein Level unverändert.

## Der Level-Generator

Damit der Bot nicht ein Level auswendig lernt, sondern das *Spielen* lernt, erzeugt
`jumpnrun/levelgen/generator.py` beliebig viele Level aus Bausteinen:

| Baustein | Beschreibung |
|---|---|
| flach | Boden, evtl. mit Gegner |
| Lücke | 1–2 Kacheln (3 nur, wenn man tiefer landet) |
| Stufe | eine Reihe hoch oder mehrere runter, auch Treppen |
| Gegner-Senke | Mulde mit Gegner, der zwischen den Wänden hin- und herläuft |
| Plattformen | Grube mit schwebenden Plattformen |

Es gibt **8 Schwierigkeitsstufen** (0 = nur zur Truhe laufen … 7 = lang, dicht, 3er-Lücken).
Jedes Level ist durch (Stufe, Seed) reproduzierbar. Die Tests prüfen Stichproben aus jeder Stufe mit dem Löser.

## Tests

`python -m pytest tests` prüft unter anderem:

- Sprunghöhe zwischen 1 und 2 Blöcken, 1er-Stufe schaffbar, 2er-Wand **nicht** (kein Klettertrick)
- Grubentod, Draufspringen, Abschießen, Schuss-Abklingzeit in Frames
- 1000 Kacheln langer Boden ohne Durchfallen (alter Chunk-Fehler)
- Determinismus: gleiche Aktionen ⇒ identischer Verlauf, auch nach `clone()` und `reset()`
- alle generierten Stichproben-Level sind lösbar

## Selbst ausprobieren

```
pip install -r requirements.txt
python game.py                                  # dein Level (Prüfungslevel)
python game.py levels/phase1/p1_luecken_01.txt  # ein Trainingslevel
python -m jumpnrun.levelgen.generator --tier 4 --seed 7 --out mein_level.txt
python game.py mein_level.txt
```
