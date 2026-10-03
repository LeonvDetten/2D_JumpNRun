# Gegenprüfung der vier Analysen, von Code-Map, Verlauf und Level-Analyse

Ich habe nur gelesen und nichts gestartet; `levels/exam2` und `milestones_exam2.json` habe ich nicht angefasst. Geprüft habe ich `curriculum.py`, `env.py`, `level.py`, `entities.py`, `sim.py`, `ppo_demos.py`, `train.py`, `status.py`, `autopilot.py`, `milestones.py` und `game.py`, außerdem `state.json`, die Meilensteine von C und D, die Lösungsdateien, die Demo-Dateien und `ps`/`taskset`.

## 0. Bestätigt (Kernaussagen halten)

- **Pool statt Generator.** `CurriculumSource.__call__` (`curriculum.py:129-136`) nimmt gespeicherte Texte, sobald eine Stufe mindestens 100 davon hat (`load_pool_texts`, Z. 40-60, `min_count=100`). `runs/demos4/demos.jsonl` enthält für die Stufen 10/11/12 genau 589/493/697 Texte, alle mit `generator: 4`.
  - Die Zeilenangabe „375-382“ der Code-Map ist falsch; die Datei hat nur 171 Zeilen.
  - Kein handgebautes Level steckt in den Demos, im Pool oder in DAgger (Stufen 0–12, keine Namen). Ein Datenleck über die Demos gibt es also nicht.
- **Prüfung 521 Spalten breit.** Die Zeilenlängen sind 374, 302, 344, 338, 294, **521**, … Rechter Rand: `entities.py:47-52` hält die Figur fest, `env.py:224` und `env.py:244` zeichnen außerhalb als fest. `to_text()` schneidet Leerzeichen am Zeilenende ab (`level.py:80`).
- **Lernrate praktisch konstant.** Bei einem Resume ist `phase_start = done` (`train.py:164`), die Abnahme läuft also über (400M − Start). Bei 62M liegt sie noch bei etwa 92 %.
- **BC-Zusatzschritte** (`ppo_demos.py:52-63`): `(coef*loss).backward()`, dann `clip_grad_norm_` und `optimizer.step()` auf demselben Adam. Der Momentum-Mechanismus der Trainings-Linse (B1) ist damit plausibel.
- **D-Nachmessung:** `36000016:raw` hat 31/33 bei Validierung 187, also dieselben Gewichte wie C-EMA 36M (43/34, 187).
- **Kernbelegung:** D läuft als ein Prozess mit 353 % CPU, Affinität 0–3, `--threads 4`, `DummyVecEnv` (`train.py:140`). Das verstößt gegen CLAUDE.md.
- **`status.py:116-119`:** „Rückschritt“ wird nur aus der Validierung abgeleitet.
- **Plateau-Leiter** (`autopilot.py:320-345`) und `state.json`: `plateaus` steht für D auf 2, `last_intervention` für D auf 0, A/B/C sind pausiert.

## 1. Fehler und Überdehnungen je Analyse

**Code-Map**
- Die Angabe „Snapshot keeps max_x“ ist missverständlich. `sim.clone()` stellt den `max_x` vom Zeitpunkt des Schnappschusses wieder her. Nach einem Rückspulen wird Fortschritt also erneut belohnt.
- Die Frage, ob der Prüfungsweg die Reihen 1–2 nutzt, ist durch die Level-Analyse beantwortet: Er nutzt sie, mit Steinen auf Reihe 2 in den Spalten 103–149.

**Verlauf, Lehre 3** („die Prüfung hängt an Ziel“)
- Das gilt nur für den Einbruch von A. In C und D liegen die meisten Abbrüche in den **Trittsteinen**:

  | Stand | Trittsteine | Ziel |
  |---|---|---|
  | C-EMA 37M | 16 | 7 |
  | C-EMA 38M | 17 | 11 |
  | C-EMA 39M | 17 | 11 |
  | D-roh 37M | 25 von 32 | 5 |
  | D-EMA 37M | 14 | 6 |

- „Ziel“ macht derzeit nur etwa 25–35 % der Abbrüche aus.

**Level-Analyse**
- „`vec[5]` im Training nie unter 0,15“ ist falsch. Das gilt nur im Stand. Beim Sprung von einer Fläche auf Reihe 3 sinkt der Wert bis etwa 0,054.
  - Wirklich neu sind zwei Dinge: Stand bei 0,077 und die Spielermarke in Reihe 0. `prow = (y+30)//60` liegt im Training mindestens bei 1.
- „Gegner 0–90 Frames vorsimulieren, damit ihr Timing variiert“ wirkt nicht. Gegner schlafen, bis der waagerechte Abstand unter 1220 px fällt (`sim.py:132-135`). Ihr Timing hängt also am Weg des Spielers, nicht an der Uhr. Vorsimulieren betrifft nur Gegner nahe am Start.

**Daten**
- **B1:** „43 vs 43 bei A34 war Zufall“ ist überzogen. Eine einzelne Gegenprobe beweist das nicht. Ehrlicher Stand: A34 liegt bei etwa 43 (43, 43, entschärft 49 und 42), C36 bei etwa 37.
- **B8 ist falsch:** Schon bei k=2 verschwindet die Marke am Sprungscheitel, wenn das Level Flächen auf Reihe 3 hat (Stand auf Reihe 1, Scheitel bei y=−78, prow=−1).
  - Die eigene Schutzregel „höchste Fläche ≥ 3+k“ hebt die Maßnahme auf: Dann liegt nach dem Anheben keine Fläche über Reihe 3, und Reihe 0–2 kommt nie vor.
  - Richtig wäre: höchste Fläche − k ≥ 2 (k=1 immer, k=2 nur ab Reihe 4) und `prow` in `env.py:268-270` auf ≥ 0 begrenzen.
- **B10 ist falsch:** Kern 3 ist nicht 80–90 % frei, das Training läuft dort mit. Damit stehen alle Durchsatzzahlen „auf Kern 3“ in Konkurrenz zum Training (ACCEL 200–900 Mutanten/h, rollierender Pool 45 Level/h, Remix 19 Kern-h).
- **(b)4** „Startversatz entkoppelt das Gegner-Timing“ ist falsch, aus demselben Grund wie oben (Aktivierung nach Abstand).
- **Rang 2** „+5 bis +10/64“ ist eine Obergrenze, keine Erwartung. Bei 5–13 Ziel-Abbrüchen sind realistisch +3 bis +8.

**Architektur**
- B5 „Ein Skalar max_x−x deckt das Loch“ ist überzogen. Er hilft dem Kritiker; die Wahl an der Gabelung muss die Politik trotzdem erst aus den Daten lernen.
- Die Angabe „0–40 leere Spalten“ ist zu schmal (siehe Abschnitt 2).
- B8 (prow<0 erst bei Flächen auf Reihe 0–1) ist korrekt und steht im Widerspruch zu Daten B8. Architektur hat recht.

**Training**
- B3 „Lernsignal nur aus ~75 Fehlschlägen pro 1M“ ist konzeptionell falsch. PPO lernt aus den Vorteilen aller Verläufe, auch der gewonnenen. Die Zahl selbst ist plausibel.
- Empfehlung 2 nutzt „Referenzlösung als Wegpunkte für handgebaute Level“. Das ist Online-DAgger auf Prüfung und Test-Serie, also Training auf dem Entwicklungs-Set. Das widerspricht den anderen Linsen.
- Empfehlung 4 und E2 („gierig mit 0–7 Leerlauf-Entscheidungen“) haben denselben Denkfehler wie oben: Deterministisch plus Leerlauf ergibt fast immer denselben Verlauf.

**Vorgaben**
- **F7, Zeitpunkt korrigieren:** D-EMA 37M hat schon neue klare Bestwerte gesetzt (Validierung 190 ≥ 187+2, Prüfung 38 ≥ 31+3). Beim 6. Meilenstein (41M) ist der Zähler also erst bei 4.
  - Frühestens beim 7. Meilenstein (~42M, grob 17–18 Uhr UTC) greift die Regel, danach bei jedem Tick erneut. Sie greift, wenn die Validierung nicht auf ≥192 und die Prüfung nicht auf ≥41 steigt.
  - Dann wird D gestoppt, die Endauswertung läuft auf dem nach Prüfung und Test-Serie gewählten Modell, und die Phase endet (`done`). Es geht nichts verloren, aber die Phase endet von selbst. Das Risiko ist also real.
- **Empfehlung 5** („deterministisch mit 0–30 Leer-Entscheidungen“) hat denselben Denkfehler. Besser: Spawn-Versatz um 0–59 px oder „sticky actions“ (mit Wahrscheinlichkeit 0,1–0,25 die vorige Aktion wiederholen, wie bei Atari üblich).
- **Empfehlung 1** („15–30 min pro Level, 24–30 Level“) schätzt den Aufwand zu niedrig.
  - Lange Level im Stil der Prüfung brauchen Stunden.
  - Menschlich lösbar heißt nicht lösbar für den Bot: Der Mensch hat jede Tastenkombination in jedem Frame (`game.py:43-47`), also links+springen und Schießen im Laufen. Der Bot hat 6 Aktionen bei 15 Hz.
  - Der Löser braucht auf handgebauten Leveln ohne Wegpunkte große Budgets.

## 2. Widersprüche und Auflösung

1. **Kern 3 frei (Daten) gegen D auf 0–3 (Training/Vorgaben):** Training und Vorgaben haben recht (siehe `ps`). Entweder das Training wieder auf 0–2 pinnen (kostet etwa 20 % Tempo) oder jede Arbeit auf Kern 3 als Training-Abzug rechnen.
2. **Leere hinter der Truhe, 0–40 (Architektur, Level-Analyse, Training) gegen 0–240 (Daten):** Die Übersicht reicht 120 Kacheln voraus. Bei 0–40 Spalten sieht der Bot weiterhin 40 Kacheln hinter der Truhe eine Wand und nie das Bild der Prüfung („120 Kacheln Leere“). Auflösung:
   - etwa die Hälfte 0–40, die andere Hälfte 120–240 Spalten;
   - im Speicher anwenden (`to_text` schneidet sonst ab) oder einen Breitenmarker setzen.
   - Einfacher und gleichwertig: in einem Teil der Level den rechten Rand als leer zeichnen und die Randbegrenzung aufheben.
3. **Anheben um 1–2 Reihen:** Die Regel der Architektur (Level mit Blöcken in den wegfallenden Reihen auslassen) stimmt, dazu kommt die Regel „höchste Fläche − k ≥ 2“. Die Regel der Daten-Linse ist falsch (siehe oben).
4. **„Prüfung hängt an Ziel“ gegen „Trittsteine 45 %“:** Beides stimmt, nur zu verschiedenen Zeiten (A-Einbruch gegen C/D). Unklar ist, wie viele der Trittstein-Abbrüche in Wahrheit Wegfehler sind: unterer Weg ab der Gabelung bei Spalte 6, Tod am Köder bei 101. Das muss vor jeder Datenänderung getrennt werden.
5. **Online-DAgger auf handgebauten Leveln (Training) gegen saubere Prüfung (alle anderen):** DAgger nur auf generierten oder neuen Trainingsleveln.
6. **„Eine Änderung pro Abzweig“ (Vorgaben, Training) gegen das Budget:** Bei 2×2 Kernen dauert ein Urteil 6–8 h. In 1–3 Tagen sind also nur 3–6 Entscheidungen möglich. Auflösung:
   - Reine Abdeckungs-Ergänzungen, die sich nicht überschneiden, gebündelt in **einem** Arm gegen eine Kontrolle testen.
   - Die Zuordnung zu einzelnen Ergänzungen liefern dauerhafte Fähigkeits-Proben (siehe Abschnitt 4).
   - Eine Änderung pro Arm nur bei Hyperparametern, Belohnung und Architektur, also bei allem, was überall wirkt.
7. **Der zweite Einbruch bei der einzigen echten Änderung (Vorgaben F8: lr 3e-5, Entropie 0) gegen „Lernrate senken hilft“ (Training):** C lief mit lr 3e-5 und Entropie 0,003 und fiel langsamer als A. Die Lernrate ist also nicht die Ursache. Am besten passt Drift; Entropie 0 ist höchstens schwach verdächtig.

## 3. Machbarkeit auf 4 CPUs

**Machbar in 1–3 Tagen:**
- alle Auswertungs-Proben (je Minuten);
- frische Stufen 10–12 und die Level-Augmentierung beim Laden;
- Abnahme der Lernrate;
- Ergänzungen von `vec` per Null-Init;
- Status- und Autopilot-Fix;
- Editor.

**Grenzwertig:**
- Online-DAgger: Die Kosten von 3–5 Kern-s pro Etappe sind ungeprüft, und mit dem BC-Gewicht 0,02 wirkt es kaum;
- PLR-light.

**Nicht in 1–3 Tagen:**
- ACCEL-light (400–600 Zeilen plus Löser-CPU);
- Remix oder Mutation der Prüfung (CPU und Testverlust);
- mitlaufende Nahsicht (Neustart, mehr als 1 Tag);
- IMPALA, PPG, getrenntes Value-Netz (1,7–3× Rechenzeit);
- POET, PAIRED.

## 4. Was fehlt (hat keine Linse genannt)

1. **Zeitablauf wird nicht bestraft.** Der Abbruch nach 600 Frames ohne Fortschritt ist `truncated`, und SB3 2.9 rechnet dort mit dem Wert des Zustands weiter (`on_policy_algorithm.py:240-245`). Festhängen in einer Sackgasse kostet im Training nichts, in der Auswertung gilt es als Niederlage.
   - Abhilfe: das Ende ohne Fortschritt als echtes Ende mit −1 werten.
   - Dann muss aber der Fortschritts-Zähler in die Beobachtung, sonst ist der Zustand nicht mehr vollständig. Das passt zu Architektur-Empfehlung 4.
2. **Gegner starten immer nach rechts und erwachen nach festem Abstand.** Das ist die billigste allgemeine Augmentierung gegen die größte Fehlerklasse „Gegner kommt entgegen“ (22–35 % der Abbrüche):
   - Startrichtung zufällig (z. B. 50 % nach links);
   - Weckabstand zufällig (z. B. 12–24 Kacheln).
   - Das ist besser als v8 oder Vorsimulieren. Ein kleiner Anteil wird unlösbar; das per Stichprobe mit dem Löser messen.
3. **Der Lehrer ist auf Tempo optimiert und knapp.** In den gespeicherten Lösungen sind 89–95 % der Aktionen „rechts“, „noop“ kommt 0–19-mal vor, bei der Prüfung 17 von 585.
   - Der Lehrer zeigt nie Warten oder Sicherheitsabstand. BC und die Starts mitten im Level übertragen also den knappsten Stil.
   - Bei zufälligem Aktionsziehen über ~1 170 Entscheidungen ist das spröde.
   - Gegenmittel: leichtes „sticky actions“ im Training (p=0,05–0,1, billig per Env-Flag) und BC nicht wieder hochdrehen.
4. **Menschliche gegen Bot-Steuerung.** Leons neue Level brauchen einen Lösbarkeitsnachweis mit den Bot-Aktionen bei Takt 2.
   - Leons aufgezeichneter Durchlauf liefert billig Wegpunkte für die Etappen-Suche (`solve_via`). Das ist besser als „Aufnahme = Beweis“.
   - Hinweis: In Phase 0 musste für das neue Spiel ein Block in die Prüfung eingefügt werden. Die Physik ist also nicht ganz die von 2023.
5. **Die Test-Serie fordert anderes als die Prüfung.**
   - festung und lange_reise brauchen laut Lösung Schüsse (je 2); die Prüfung braucht keinen.
   - hoehle hat massive Reihen 0–1. In der Übersicht ist das von „außerhalb des Levels“ kaum zu unterscheiden, denn außen wird als fest gezeichnet.
   - Eine Verbesserung auf der Prüfung muss sich deshalb nicht auf die Test-Serie übertragen. Beide getrennt berichten.
6. **Validierung deterministisch, Prüfung und Test-Serie zufällig.** Der Vergleich r = −0,12 mischt zwei Auswertungsarten. Mindestens einmal die Validierung zufällig und die Prüfung mit Spawn-Versatz deterministisch messen.
7. **Dauerhafte Fähigkeits-Proben statt Einzelversuchen.** Feste, generierte Probe-Sets je Fähigkeit in jeden Meilenstein aufnehmen, je 40 Level, zum Beispiel:
   - Truhe vor Leere;
   - Steine auf Reihe 2;
   - Gegner kommt die Treppe herab;
   - Gabelung mit Köder.

   Sie streuen weniger als die Prüfung und verbrauchen sie nicht.
8. **Sichern vor dem Umbau** („ohne dass etwas verloren geht“):
   - git-Tag setzen;
   - A34-EMA, C36-EMA und D-Stände nach `models/phase7_*` kopieren;
   - `runs/phase7*` unverändert lassen;
   - der BC-Cache braucht bei neuer Beobachtung einen neuen Dateinamen (`demos.py:165-173`).
9. **Autopilot vor der Reflexionspause entschärfen.** Leon entscheidet: STOP-Schutz oder Zähler zurücksetzen. Sonst endet die Phase von selbst (siehe 1, Vorgaben).

## 5. Urteil je Empfehlung

**Daten**

| Empfehlung | Urteil | Bemerkung |
|---|---|---|
| R1 Datenweg reparieren | keep | Pflicht. Ankunft über `blocks` prüfen; je Abzweig eigener Seed. |
| R2 Level-Augmentierung | modify | Leere 0–40 und 120–240; Anheben mit Regel „höchste Fläche − k ≥ 2“; `prow` begrenzen; Startversatz streichen, dafür Gegnerrichtung und Weckabstand zufällig; Start ohne P beibehalten. |
| R3 Schicht für Gegner, Decken und Köder | modify | Zuerst der billige Teil aus Abschnitt 4, Punkt 2; die Regel für Gegnerbahnen später. |
| R4 PLR-light | defer | |
| R5 ACCEL-light | drop | für 1–3 Tage |
| R6 Remix/Mutation der Prüfung | drop | höchstens als getrennter Diagnose-Ableger nach dem Einfrieren der Prüfungszahl |
| R7 gelernte Erzeugung | drop | |
| R8 Beobachtungs-Augmentierung (DrQ/RAD) | drop | |
| R9 POET/PAIRED | drop | |
| X1 Rand-Probe | keep | Höchste Priorität, mit Architektur-E1 zusammenlegen. |
| X2 Höhen-Probe | modify | mit der korrigierten Anheberegel |
| X3 Abdeckungs-Probe | keep | |

**Architektur**

| Empfehlung | Urteil | Bemerkung |
|---|---|---|
| 1 Erst E1/E2 | keep | |
| 2 Invarianz-Augmentierung | modify | wie Daten R2 |
| 3 Daten, die die Fernsicht erzwingen | keep | nach der Trennung der Trittstein-Abbrüche nach Weg |
| 4 Ergänzungen der Beobachtung | keep | zusammen mit „Zeitablauf als Ende“ |
| 5 Mitlaufende Nahsicht | drop | vorerst |
| 6 Getrenntes Kritiker-Netz | drop | vorerst |
| Strategische Option Weg-Karte | Leons Entscheidung | eher nein, verschiebt Intelligenz in Handcode |

**Training**

| Empfehlung | Urteil | Bemerkung |
|---|---|---|
| 0 Ankunft und Kontrolle | keep | |
| 1 Lernrate abklingen lassen, zweites EMA | keep | in beiden Armen gleich |
| 2 BC dauerhaft 0,1 und Online-DAgger | modify | Die 12 BC-Extra-Schritte streichen oder in den PPO-Minibatch legen. BC 0,1 nur als eigener Arm. DAgger nur auf generierten Leveln, später. |
| 3 Mehr Envs | keep | niedrige Priorität |
| 4 Auswertung | modify | Spawn-Versatz oder sticky actions statt Leerlauf; `status.py` soll Prüfungs-Rückschritte erkennen. |
| 5 KL-Anker | defer | erst wenn ein echter Datenwechsel einen Einbruch zeigt |
| 6 Vorausschau | Leons Entscheidung | nur als getrennte Wertung |
| 7 PPG, Value-Netz, PLR | drop | vorerst |
| E1 Drift-Sonde | keep | |
| E2 Auswertungsmodus | modify | wie Empfehlung 4 |
| E3 Datenwirkung mit Kontrolle | keep | als gebündelter Arm |

**Vorgaben**

| Empfehlung | Urteil | Bemerkung |
|---|---|---|
| 1 Neue Sammlung H | modify | Pilot 3–4 Level; dann 10–15 kurze und mittlere Level von Leon und Claude-Level in neuen Stilen, getrennt ausgewiesen. Lösbarkeit über Leons Aufnahme als Wegpunkte für den Löser. 24–30 Level als Fernziel. |
| 2 Feste Entscheidungsregeln | modify | Abdeckungs-Ergänzungen bündeln (Abschnitt 2, Punkt 6) |
| 3 Status und Autopilot reparieren | keep | sofort, F7-Zeitpunkt korrigiert |
| 4 Modellwahl und Endzahl vorab festlegen | keep | |
| 5 Kennzahlen ändern | modify | Spawn-Versatz statt Leerlauf |
| 6 Berichtstakt | keep | |
| 7 Prüfung als Saatgut erst nach dem Einfrieren | keep | |
| 8 Level-Werkzeuge | keep | Die Aufnahme liefert Wegpunkte, keinen Beweis. |
| E1 Größe des Siegerfluchs | keep | |
| E2 Deterministisch oder zufällig | modify | mit Spawn-Versatz |
| E3 Pilot für H | keep | |

## 6. Vorschlag für die Reihenfolge

1. **Sichern** (Abschnitt 4, Punkt 8) und den Autopilot entschärfen (Leons Entscheidung).
2. **Proben auf Kern 3, zusammen etwa 1 h:**
   - Rand-Probe X1/E1: Wand statt Leere hinter der Prüfungs-Truhe; Leere und k=1 auf Validierung v4;
   - Trittstein-Abbrüche nach Weg trennen (Reihe zwischen Spalte 40 und 97);
   - 256 Versuche für A34 und C36;
   - zufällig gegen deterministisch mit Spawn-Versatz.
3. **Ein gebündelter Daten-Arm gegen eine Kontrolle**, je 2 Kerne, mindestens 5M Schritte, mit Fähigkeits-Proben:
   - frisches v8;
   - Leere hinter der Truhe;
   - k=1 anheben;
   - Start ohne P;
   - Gegnerrichtung und Weckabstand zufällig;
   - Lernrate mit Kosinus in beiden Armen.
4. **Danach ein zweiter Arm:** `vec` um `max_x−x` und den Fortschritts-Zähler ergänzen, Zeitablauf als Ende mit −1.
5. **Parallel:** Leon baut den Pilot für H.

Dateien: /home/user/2D_JumpNRun/jumpnrun/rl/autopilot.py, /home/user/2D_JumpNRun/runs/phase7/state.json, /home/user/2D_JumpNRun/jumpnrun/rl/env.py, /home/user/2D_JumpNRun/jumpnrun/core/sim.py, /home/user/2D_JumpNRun/jumpnrun/rl/curriculum.py, /home/user/2D_JumpNRun/jumpnrun/rl/ppo_demos.py, /home/user/2D_JumpNRun/jumpnrun/rl/status.py, /home/user/2D_JumpNRun/game.py, /home/user/2D_JumpNRun/runs/phase7d/milestones.json, /home/user/2D_JumpNRun/runs/phase7c/milestones.json, /home/user/2D_JumpNRun/levels/test_serie/