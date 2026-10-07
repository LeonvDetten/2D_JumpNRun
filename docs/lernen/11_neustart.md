# Lerntagebuch 11 – Neustart: ein frisches Netz neben Phase 10

Rohdaten und Regeln: `docs/lernen/daten/neustart_vorregistrierung.json` (alle Schwellen, vor dem ersten
PPO-Schritt committet), `docs/lernen/daten/neustart_profiling.json`, `docs/lernen/daten/neustart/` (Meilensteine,
Drift, Autopilot-Zustand, Statusbild), Code `jumpnrun/rl/neustart_bc.py`, `autopilot_neustart.py`,
`status_neustart.py`. Kandidaten für den gepaarten Endvergleich: `models/neustart_kandidat_*.zip`.

## Ausgangslage

Phase 10 trainierte das Phase-8-Modell (P8) weiter auf neue Fähigkeiten (Umkehren, Kanäle, Truhe links,
links+springen). Die neuen Fähigkeiten kamen an, aber im Tausch gegen alte: dev_alt 61–65 % statt 66,4 %,
Wächter 50–65 % statt 77 %. Leon entschied am 6. Oktober, parallel zu Runde C einen **Neustart-Arm** zu fahren:
frische Gewichte statt P8 weitertrainiert. Gründe: Nach ~50 Mio. Schritten Rechts-Training probiert das Netz
„links“ kaum noch (*primacy bias*: ein lange trainiertes Netz lernt Neues schlechter), und das Nachtrainieren
erzeugte den Alt/Neu-Konflikt.

## Vor dem Start gefunden

| Befund | Folge |
|---|---|
| Container-Python 3.13 stürzt beim Laden der Modelle ab (in Python 3.11 gespeicherte Lernraten-Funktionen) | `scripts/setup_neustart.sh`: eigene Umgebung mit Python 3.11 und exakt den Paketversionen der Modelle |
| Das PPO-Update braucht 68–75 % der Zeit, das Spiel nur 5–7 % | `channels_last` (andere Speicheranordnung der Faltungsgewichte): Update 1,5× schneller, gleiche Ausgaben |
| Ein frisches Netz mit Tanh-Köpfen (wie P8) lernt beim Nachahmen nur „immer rechts“ | ReLU-Köpfe, sonst gleiche Architektur |
| Gespiegelte Phase-9-Demos wurden mit falscher Gegnerrichtung nachgespielt: 34 von 51 endeten nicht im Sieg; sie stellen 18 % aller links+springen-Beispiele (betraf auch Phase 10) | Gegnerrichtung beim Nachspielen gesetzt; Demos, die nicht gewinnen, werden verworfen |
| Alle Lehrer-Beispiele hatten „Schritte ohne Fortschritt“ = 0 und „Zeit übrig“ = 100 % fest | Neu gerendert mit der Buchführung des Trainings |
| Die Übungsstufen wurden je Env verfolgt und gingen bei jedem Neustart verloren | zentral im Trainingsprozess, gespeichert in `curriculum.json` |

Vier unabhängige Prüfer (RL-Methodik, Messung, Code, Betrieb) haben den Plan vor dem Start gegengelesen. Ihre
wichtigsten Korrekturen: Die ursprüngliche Startprüfung (dev_alt ≥ 20 %) war für ein frisches Netz nicht
erreichbar; die Abbruchschwellen hätten sogar die Phase-10-Arme gestoppt; das Erfolgskriterium „Alt ≥ P8 − 3 Pp“
verglich Ungleiches (Alt enthält den Wächter, die P8-Basis nicht) – jetzt gilt das unveränderte Phase-10-Tor.

## Leons Entscheidungen (Planmodus)

- **Ein Arm** auf allen Kernen: Löser-Nachahmen als Start, dann PPO mit **Kickstarting** von P8.
  *Kickstarting* heißt: Auf den eigenen Spielzuständen in Phase-8-Leveln (ohne Gabeln und Kanäle, dort ist P8 der
  falsche Lehrer) wird das Netz zusätzlich zu P8s Entscheidungen gezogen; das Gewicht fällt von 1 auf 0 über
  15 Mio. Schritte. links+springen bleibt frei, weil nur über die 6 alten Aktionen verglichen wird.
- Lernrate 2e-4 → 2e-5 (Kosinus über 45 Mio.), Mischung Phase-8-Level 60 % / Übung 20 % / lange v10-Level 20 %
  (v10 erst ab Curriculum-Stufe 10).
- Grenze 45 Mio. Schritte oder 60 h; Abbruchregel bei +5/+15/+30 Mio. (vorregistriert).

## Verlauf

- **BC-Start** (06.10. 10:57–11:32): 16 000 Schritte Nachahmen. Holdout 0,986 (Basis „immer rechts“ 0,681),
  auf Zuständen ohne „rechts“ 0,975, P(links+springen) auf links+springen-Zuständen 0,95, auf alten Zuständen
  0,002, Validierung 37,5 %. Volle Messung des Startnetzes: dev_alt 13,9 %, dev_neu 18,8 %, Prüfung 0/64.
- **PPO-Start** 11:32. Ein Neustart der Sitzung beendete das Training bei 1,3 Mio. (12:18); fortgesetzt 14:16.
- **Engpass Betrieb:** Teilte sich der 4-Thread-Trainer einen Kern mit der (einfädigen) vollen Messung, fiel er
  von ~540 auf ~35–90 Schritte/s – nice 10 und die Leerlauf-Klasse halfen nicht. Seit 16:32 trainiert der Arm auf
  den Kernen 0–2, Messung und Autopilot laufen auf Kern 3: ~550 Schritte/s ohne Einbrüche.

| Mio. Schritte | dev_alt (EMA) | F | dev_neu | Wächter | Prüfung | Bemerkung |
|---|---|---|---|---|---|---|
| 1 | 17,1 % | 26,5 % | 17,2 % | – | 0/32 | |
| 2 | 36,4 % | 29,8 % | 4,7 % | 0 % | 0/64 | Curriculum Stufe 10, v10 offen |
| 3 | 41,2 % | 25,3 % | 4,7 % | – | 1/32 | |
| 4 | 47,0 % | 32,2 % | 8,6 % | 6,2 % | 1/64 | |
| 5 | 48,9 % | 36,2 % | 12,5 % | – | 0/32 | Abbruchregel +5 Mio. bestanden (dev_alt 46,8 %, F 33,5 %) |
| 6 | 49,7 % | 38,3 % | 14,8 % | 14,1 % | 4/64 | Schutz 63/80 |
| 8 | 51,8 % | 42,7 % | 19,5 % | 21,1 % | 13/64 | Kickstart-Gewicht 0,45 |
| 10 | 53,3 % | 39,5 % | 15,6 % | 29,7 % | 13/64 | |
| 12 | 57,1 % | 39,4 % | 17,2 % | 18,0 % (EMA2 30,5 %) | 12/64 (EMA2 22) | |
| 14 | 54,4 % | 39,9 % | 16,4 % | 32,0 % | 11/64 | Plateau-Frage an Leon |
| 15 | – | – | – | – | – | Abbruchregel +15 Mio. bestanden (dev_alt 54,3 %, F 35,1 %); Lehrer aus |
| 16 | 61,8 % | 44,3 % | 21,1 % | 41,4 % | 17/64 | ohne Lehrer weiter aufwärts |
| 20 | 63,3 % | 45,5 % | 21,1 % | 33,6 % (EMA2 54,7 %) | 10/64 (EMA2 24) | |
| 24 | 61,9 % | 42,3 % | 18,8 % | 43,8 % (EMA2 55,5 %) | 20/64 (EMA2 27) | |
| 26 | 60,4 % | 48,0 % | 22,7 % | 50,0 % (EMA2 61,7 %) | 11/64 | |
| 28 | 68,0 % | 42,2 % | 21,1 % | 60,2 % (EMA2 75,0 %) | 23/64 | dev_alt über P8-Basis |
| 30 | 66,0 % | 40,5 % | 10,2 % | 49,2 % (EMA2 73,4 %) | 23/64 (EMA2 26) | Abbruchregel +30 Mio. bestanden (dev_alt 66,9 %, Wächter 64,5 %, F 43,0 %) |

Zum Vergleich: Die P8-Linie (PPO ab frisch, ohne Kickstarting) lag bei 24 % nach 11 Mio. und 40 % nach 30 Mio.;
Phase-10-Runde B bei +6 Mio. bei dev_alt 58–60 % und F 40–41 % – mit 50 Mio. Schritten Vorsprung.

Beobachtungen unterwegs:
- **dev_neu hängt an einem Level.** Von den 4 neuen Dev-Leveln wird nur „serpentine“ gewonnen; gabel_drei, kreuzung
  und spiegelweg blieben in jeder Messung bei 0 – wie in Phase-10-Runde B. Das Auf und Ab von dev_neu (3–25 %) ist
  das Schwanken dieses einen Levels.
- **Kein Abfärben des Umkehrens.** P(links+springen) auf alten Zuständen blieb über den ganzen Lauf bei 0,01–0,24 %,
  auch nachdem das Kickstarting-Gewicht auf 0 gefallen war. Die Drift-KL zu P8 stieg danach auf ~0,2 – das Netz geht
  eigene Wege, ohne dass dev_alt leidet.
- **EMA2 ist auf langen Leveln deutlich besser** als EMA (Wächter 73–75 % gegen 49–60 % bei 28–30 Mio.).
- **Alt-Tor (select10-Fenster):** dev_alt erfüllt es ab 28 Mio., der Wächter (Fenstermittel 64,5 % bei 30 Mio.)
  noch nicht (verlangt 72,3 %).
- **Tempo:** von ~550 Schritte/s (Stufen bis 10) auf ~360 Schritte/s ab ~20 Mio. (vermutlich längere Level auf
  Stufe 12). Zwei weitere Sitzungs-Neustarts (19,4 Mio.) kosteten nur Minuten.

| Mio. Schritte | dev_alt EMA / EMA2 | F EMA / EMA2 | Wächter EMA / EMA2 | Prüfung EMA / EMA2 (von 64) |
|---|---|---|---|---|
| 32 | 66,9 / 67,2 % | 43,1 / 46,7 % | 57,8 / 64,1 % | 21 / 27 |
| 34 | 67,2 % / – | 43,6 % / – | 53,9 % / – | 23 / – |
| 36 | 66,9 / 69,6 % | 46,3 / 47,6 % | 57,0 / 58,6 % | 29 / 32 |
| 38 | 70,5 / 70,0 % | 46,8 / 48,4 % | 69,5 / 64,8 % | 38 / 39 |
| 40 | 65,6 / 68,8 % | 46,4 / 46,8 % | 70,3 / 70,3 % | 32 / 34 |
| 42 | 64,5 / 68,5 % | 45,2 / 45,5 % | 58,6 / 71,1 % | 32 / 34 |
| 44 | 71,3 / 67,5 % | 48,8 / 44,3 % | 58,6 / 63,3 % | 42 / 31 |

Ende: 45 Mio. Schritte am 07.10. um 18:23 UTC (≈ 31 h Wanduhr ab PPO-Start, Grenze 60 h).

## Ergebnis (ohne versiegelte Werte)

- **Alle drei Abbruchregeln bestanden** (+5 Mio.: dev_alt 46,8 %, F 33,5 %; +15 Mio.: 54,3 % / 35,1 %;
  +30 Mio.: dev_alt 66,9 %, Wächter 64,5 %, F 43,0 %).
- **Alt-Tor aus Phase 10 (select10-Fenster): 0 von 44 Ständen.** dev_alt erfüllt es ab ~28 Mio. durchgehend
  (Fenster 67–69 %), der Wächter nicht: bestes Fenster 67,4 % bei 40 Mio. (verlangt 72,3 %). Phase 10 scheiterte
  am selben Engpass (0 von 32, beste Wächter-Fenster 65–70 %).
- **Kandidaten** (in `models/`, mit Messwerten in der Begleitdatei):

  | Kandidat | Stand | dev_alt | F | Wächter | Prüfung |
  |---|---|---|---|---|---|
  | `neustart_kandidat_f` | EMA2 38 Mio. (bestes F-Fenster) | 70,0 % | 48,4 % | 64,8 % | 39/64 |
  | `neustart_kandidat_waechter` | EMA2 40 Mio. (bestes Wächter-Fenster) | 68,8 % | 46,8 % | 70,3 % | 34/64 |
  | `neustart_kandidat_pruefung` | EMA 44 Mio. | 71,3 % | 48,8 % | 58,6 % | 42/64 |

- **Vergleich mit Phase 10** (gleiche Messung, Seed 0 – je eine volle Messung, also verrauscht; der gültige
  Vergleich ist der spätere gepaarte Endvergleich):

  | | dev_alt | F | Wächter | Prüfung |
  |---|---|---|---|---|
  | P8 (Basis) | 66,4 % | ≈ 8 % | 77,3 % | 44–52/64 |
  | Phase 10 Kandidat Alt (Kontrolle EMA2 +6 Mio. Runde C) | 66,5 % | 43,5 % | 69,5 % | 46/64 |
  | Phase 10 Runde D (P8 als Lehrer, EMA2 +6 Mio.) | 67,5 % | 43,4 % | – | 51/64 |
  | Neustart Kandidat F (EMA2 38 Mio.) | 70,0 % | 48,4 % | 64,8 % | 39/64 |

  Der Neustart liegt bei dev_alt (+3 Pp) und F (+5 Pp) vorn, beim Wächter etwa gleich, bei der Prüfung hinten
  (39–42 gegen 46–51 von 64).

## Was wir daraus lernen

1. **Ein frisches Netz holt das P8-Niveau in ~30 Mio. Schritten zurück** – mit Löser-Nachahmen als Start und
   Kickstarting von P8. Die P8-Linie brauchte dafür ~50 Mio. Schritte und mehrere Phasen.
2. **Das Umkehren färbte nicht ab.** P(links+springen) auf alten Zuständen blieb nahe 0, auch ohne Lehrer.
   Alt und Neu wurden gemeinsam gelernt statt gegeneinander getauscht – die Kernhoffnung des Neustarts.
3. **Die Gewinne auf langen Leveln kamen spät,** mit sinkender Lernrate (Wächter 30 % bei 15 Mio., 65–70 % ab 38 Mio.).
   EMA2 war dort meist besser als EMA.
4. **F bleibt bei ~45–48 % hängen:** Von den 4 neuen Dev-Leveln gewann kein Ansatz je gabel_drei, kreuzung oder
   spiegelweg. Das ist eine Grenze der Trainingsdaten, nicht des Neustarts.
5. **Betrieb:** Ein 4-Thread-Trainer, der einen Kern mit der einfädigen Messung teilt, bricht auf ~5 % seines
   Tempos ein; eigene Kerne für Messung und Training lösen das. Ein frisches Netz mit Tanh-Köpfen lernt beim
   Nachahmen nur „immer rechts“.

*Offen: der gepaarte Endvergleich mit Phase 10 (versiegelte Gruppe, einmalig) – Leons Entscheidung.*

*(Fortsetzung folgt.)*
