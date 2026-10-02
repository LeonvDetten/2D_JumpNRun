# Reflexion nach Phase 7 und Vorschlag für Phase 8

Für diese Reflexion wurde nur gelesen und ausgewertet. Gelöscht oder überschrieben wurde nichts, `levels/exam2` blieb ungeöffnet. Lauf D trainiert weiter.

## 1. Kurzfazit

- **v5 bis v8 kamen nie im Training an.** Sobald eine Stufe mindestens 100 gespeicherte Level hat, nimmt das Training diese gespeicherten Level und erzeugt keine neuen. Für die Stufen 10–12 waren das 1 779 Level aus Generator v4. Dass „jede Datenänderung die Prüfung erst senkt“, ist damit nicht belegt. Die Einbrüche kamen von Drift und Messrauschen.
- **Der Bot verallgemeinert gut, aber nur innerhalb der Generator-Welt.** Auf nie gesehenen generierten Leveln schafft er 195–200 von 200. Auf der Prüfung fiel Lauf A gleichzeitig von 43 auf 1–11 von 64. Die beiden Werte hängen nicht zusammen (r = −0,12).
- **Die Prüfung verlangt Dinge, die es im Training nicht gibt.** Dort steht die Truhe vor einem Abgrund, im Training ist der Levelrand immer eine Wand. Es gibt Steine auf Reihe 2, im Training liegt nie etwas höher als Reihe 3. Und der Bot startet in der Luft. Für diese Stellen legt kein Trainingssignal das Verhalten fest, deshalb driftet es.
- **Netz und Lernverfahren sind im Kern richtig.** Ein paar Stellschrauben stimmen nicht: Die Lernrate klingt nie ab, die Nachahm-Hilfe wirkt kaum, Festhängen wird nicht bestraft, und der Beobachtung fehlen einige Zahlen.
- **Unsere Messung ist zu schwach für deine Frage.** Eine Prüfungsmessung schwankt um ±4 Siege. Sieben handgebaute Level reichen statistisch nicht, und nur eins davon stammt von dir. Die Status-Auswertung hat den Einbruch nie als „Rückschritt“ gemeldet. Der größte Hebel für Phase 8 ist deshalb ein ehrliches Messsystem.

## 2. Was die Daten zeigen

| Befund | Beleg |
|---|---|
| Neue Bausteine im Training | 0. Alle Episoden der Stufen 10–12 waren gespeicherte v4-Level |
| Drift ohne Datenänderung | Lauf A, 37–39 Mio. Schritte: Prüfungsmittel 38,8 → 15,3, Ziel-Abschnitt 0,96 → 0,20 |
| Messrauschen | 64 Versuche schwanken um ±4 Siege. Zwei Einzelmessungen unterscheiden sich erst ab etwa 10 Siegen wirklich |
| Glückstreffer bei der Auswahl | C-EMA 36M ergab 43/64. Dieselben Gewichte wurden als Start von D nachgemessen und ergaben 31/64 |
| Test-Serie | Die ganze Phase 7 flach bei 60–65/96. Drei Level sind fast gelöst (44/48), drei hängen: festung, hoehle, lange_reise mit 18,5/48 |
| Abbrüche auf der Prüfung (C/D) | Trittsteine etwa 45 %, Ziel etwa 25–35 % |
| Tod durch Gegner | 22 % der Abbrüche auf der Prüfung, 35 % auf der Test-Serie |
| Lernrate | nach 62 Mio. Schritten noch bei 92 % des Startwerts, weil die Abnahme auf 400 Mio. Schritte ausgelegt ist |
| Fernsicht | Werden die Übersichtskarten zwischen Zuständen vertauscht, ändern sich nur 9,8 % der Aktionen. Im Generator ist der obere Weg immer richtig oder gleichwertig, die Karte wird also nie gebraucht |

Die Abschnitts-Statistik zählt nur nach Spalte. Ein Teil der „Trittstein“-Tode ist vermutlich ein Wegfehler: Der Bot nimmt bei Spalte 6 den unteren Weg und stirbt am Köderblock bei Spalte 101. Das trennen wir, bevor wir dafür Daten bauen.

## 3. Frage 1: Level aus deinem Prüfungslevel und Data Augmentation

**Kurz: Ja zur Augmentierung, nein zum Kopieren der Prüfung.** Technisch wäre ein Remix leicht, denn es gibt den Löser, eine deterministische Simulation und eine gespeicherte Lösung. Aber jedes Level, das aus der Prüfung entsteht, macht sie zu Trainingsdaten. Danach misst sie, ob der Bot wiedererkennt, und nicht, ob er verallgemeinert. Übertragen wir also die **Situationen** der Prüfung, nicht ihre Geometrie.

| Idee | Urteil | Grund |
|---|---|---|
| Prüfung zerschneiden, neu mischen, abwandeln | nein, höchstens als getrennter Diagnose-Lauf | Die Prüfung wäre als Test verbraucht. Aus rund 40 Stücken lernt der Bot eher auswendig |
| Erzeugung lernen (Markov, WFC, GAN) | nein | Etwa 13 handgebaute Level sind viel zu wenig, und solche Verfahren kennen keine Weglogik |
| Bild-Augmentierung (verschieben, verrauschen, spiegeln) | nein | Sprünge brauchen kachelgenaue Bilder. Spiegeln geht nicht, weil das Ziel rechts liegt und es kein „links + springen“ gibt |
| **Augmentierung im Level selbst** | **ja, zuerst** | Die Physik bleibt korrekt. Ob ein Level lösbar bleibt, zeigt das Nachspielen der gespeicherten Lösung in Sekunden |
| Situationen als neue Generator-Schichten | ja | Allgemein formuliert, die Prüfung bleibt aussagekräftig |
| **Neue echte Level von dir** | **ja, der beste Weg** | Die einzige Quelle wirklich handgemachter Vielfalt |

Diese Augmentierungen würden beim Laden jedes Levels angewendet:
- **Leere hinter der Truhe:** Die Truhe steht auf der letzten Bodenkachel. Bei der Hälfte der Level folgen 0–40 leere Spalten, bei der anderen Hälfte 120–240, weil die Übersicht 120 Kacheln weit reicht.
- **Level um eine Reihe anheben**, damit die Reihen 0–2 vorkommen. Um zwei Reihen nur, wenn das Level es zulässt.
- **Massive Decke in Reihe 0–1** wie in „hoehle“.
- **Start in der Luft**, also ohne Startpunkt P.
- **Gegner:** zufällige Startrichtung und ein zufälliger Weckabstand von 12–24 Kacheln statt der festen ~20. Das ist die billigste Antwort auf Gegner, die dem Bot entgegenkommen. Ein kleiner Teil der Level wird dadurch unlösbar. Wie groß, messen wir mit einer Löser-Stichprobe.

Am Start zu warten bringt nichts, weil Gegner nach Abstand aufwachen und nicht nach Zeit.

**Was das für die Prüfung bedeutet:** Sie ist faktisch schon ein Entwicklungs-Set. Generator-Fixes kamen aus ihrer Fehleranalyse, und Modelle wurden nach ihr ausgewählt. Deshalb frieren wir zuerst eine letzte saubere Zahl ein: ein vorher festgelegtes Modell, 128 Versuche, fester Seed. Den Nachweis der Verallgemeinerung übernehmen danach `exam2` und neue Level.

Eine Frage an dich: Gehört „Truhe vor dem Abgrund“ zur Prüfung? Meine Empfehlung ist ja, denn ein Mensch sieht den Abgrund ebenfalls. Dann muss die Situation aber auch im Training vorkommen.

## 4. Frage 2: Architektur und Trainingsart

**Behalten:**
- PPO zusammen mit dem Nachahmen des Lösers. Phase 5 hat das belegt: nur Nachahmen 64/120, nur PPO 83/120, beides 114/120.
- Das CNN mit Übersichtskarte.
- Eine Entscheidung alle 2 Frames.

Die Kapazität des Netzes reicht (200/200). Ein größeres Netz würde nur die Generator-Welt noch genauer treffen.

**Nicht machen:**
- IMPALA: gemessen 115 statt 430 Schritte pro Sekunde, und das Pooling verwischt die genaue Kachelposition.
- LSTM: Der Zustand lässt sich fast ohne Gedächtnis entscheiden.
- Transformer: etwa der 8-fache Rechenaufwand.
- Mitlaufende Nahsicht und ein getrenntes Kritiker-Netz: vorerst nicht.

**Ändern:**

| Änderung | Warum |
|---|---|
| Lernrate wirklich abklingen lassen (Kosinus-Kurve auf 10 % über die Phasenlänge), dazu ein zweites, langsames EMA | Bremst die Drift. Eine neue Fähigkeit entsteht dadurch nicht |
| Die 12 Zusatzschritte für das Nachahmen pro Update streichen oder in den normalen PPO-Schritt einbauen | Bei Gewicht 0,02 schieben sie vermutlich nur das Momentum des Optimierers weiter, ohne PPOs Schutzgrenze |
| Festhängen (600 Frames ohne Fortschritt) als echtes Ende mit −1 werten | Heute kostet Festhängen im Training nichts, in der Auswertung zählt es als Niederlage |
| Beobachtung um einige Zahlen ergänzen, eingebaut so, dass neue Eingänge mit Gewicht 0 starten und das Verhalten anfangs gleich bleibt | Hilft beim Rückweg aus Sackgassen und beim Timing gegen Gegner. Neu sind: Abstand zum bisher weitesten Punkt, verbleibende Frist, Gegner überschreiben sich nicht mehr, Gegner-Plätze nur für Gegner voraus, mit Fallgeschwindigkeit |
| Fernsicht über die Daten erzwingen statt über eine neue Architektur | Dafür bauen wir Gabelungen, bei denen die Sackgasse oben liegt |

**Zwei Grundsatzfragen an dich:**
- Vorausschau beim Spielen, bei der der Bot ein Stück vorausrechnet: nur als getrennte Wertung „Netz + Vorausschau“. Sonst wäre die Prüfung mit dem Löser trivial.
- Eine vom Programm berechnete Wegkarte als Eingabe: eher nein. Damit steckt die Intelligenz in handgeschriebenem Code.

## 5. Frage 3: Deine Vorgaben

**Behalten:** Die Prüfung wird nie trainiert. Training über Skripte mit Zeitlimit, die Wächter-Routine und regelmäßige Zwischenstände zum Zusehen.

**Ändern:**
1. **Zwischenstände alle 30 Minuten nur als Status**, mit dem Hinweis „nächster Entscheidungspunkt bei Meilenstein N“. Vorschläge für Eingriffe gibt es nur an Entscheidungspunkten (etwa alle 4 EMA-Meilensteine, also alle ~3 h) oder bei einem echten Rückschritt. In Phase 7 gab es 5 Eingriffe in 18 h, zwei davon nur 9 Minuten auseinander.
2. **Jeder Eingriff als Ableger mit einem Kontroll-Ableger.** Beide starten am selben Punkt, die Kontrolle behält die alten Einstellungen, jeder bekommt 2 Kerne.
   - Pro Arm ändern wir genau eine Sache, wenn es um Lernparameter, Belohnung oder Netz geht. Reine Daten-Ergänzungen dürfen wir bündeln.
   - Geurteilt wird frühestens nach 5–8 Mio. Schritten.
   - Innerhalb von 30 Minuten prüfen wir, ob die Änderung im Training ankommt.
3. **Nie an einem einzelnen Höchstwert abzweigen.** Den Startpunkt messen wir vorher mit 256 Versuchen nach.
4. **Status und Autopilot reparieren:**
   - „Rückschritt“ wird an Prüfung und Test-Serie gemessen, und zwar am Mittelwert über mehrere Meilensteine.
   - Die Plateau-Regel meldet nur noch und fragt nach, statt selbst einzugreifen.
5. **Messprotokoll mit vier Gruppen:**

| Gruppe | Inhalt | Nutzung |
|---|---|---|
| Entwicklung | Prüfung, Test-Serie, 1/3 der neuen Level | Fehleranalyse, Modellwahl |
| Test (H) | 1/3 der neuen Level | nur Gesamtsiege, keine Analyse |
| Versiegelt | `exam2` und 1/3 der neuen Level | nur für das vorab gewählte Modell, einmal am Ende |
| Schutz | Validierung, gekürzt | nur als Alarm gegen Vergessen |

   - **Hauptwert:** die mittlere Erfolgsrate je Level mit 95-%-Intervall und festen Seeds.
   - **Warum mehr Level nötig sind:** Die Level unterscheiden sich so stark, dass der Mittelwert über 7 Level um ±0,12 unsicher bleibt, egal wie oft man spielt. Bei 30 Leveln sind es ±0,06.
   - **Achtung bei `exam2`:** Es läuft heute bei jedem Meilenstein mit. Den Höchstwert daraus dürfen wir nicht als Ergebnis nehmen.
6. **Kriterium für `main`:** Die untere 95-%-Grenze muss bei 128 Versuchen mindestens 50 % sein, also mindestens 76 von 128. Das gilt auf dem versiegelten Teil, nicht auf der Entwicklungs-Prüfung.
7. **Kernbelegung einhalten:** D läuft derzeit auf allen vier Kernen.

## 6. Vorschlag Phase 8

Deine drei Punkte sind alle enthalten, in angepasster Form:
- Der **kombinatorische Generator** wird zu Schichten über jedem Level: Gegnerverhalten, Decken, Köder-Gabelungen, Steine auf Reihe 2, lange Steinketten.
- **Prioritized Level Replay (PLR)** kommt als zweite Stufe. PLR spielt Level öfter, an denen der Bot am meisten lernt. Es braucht erst Level-Namen im Pool und verteilt nur innerhalb der Generator-Welt um.
- **Mehr unabhängige Testlevel** sind die Gruppe H.

Wenn du viel investieren willst, ist deine Zeit für eigene Level wertvoller als zusätzliche Rechenzeit.

**Zuerst billige Proben** (nur Auswertung, zusammen 1–2 h):
1. Prüfung mit Wand statt Leere hinter der Truhe gegen das Original, je 128 Versuche. Dazu die Validierung mit Leere hinter der Truhe und um eine Reihe angehoben.
2. Trittstein-Abbrüche nach Weg trennen, also oben oder unten.
3. A-EMA 34M und C-EMA 36M mit je 256 Versuchen nachmessen.
4. Zufällige Aktionswahl gegen feste Wahl mit leicht versetztem Start vergleichen.
5. 300 frische v8-Level nach Baustein aufschlüsseln.

| | **A „Daten-Fokus“ (empfohlen)** | B „Lehrer-Fokus“ | C „Komplett“ |
|---|---|---|---|
| Inhalt | Datenweg reparieren, Level-Augmentierung, erste Generator-Schicht, abklingende Lernrate, Fähigkeits-Proben*. Ein Daten-Arm gegen eine Kontrolle. Danach ein zweiter Arm mit Beobachtung und „Festhängen = −1“. Dann PLR | Nachahmen dauerhaft mit Gewicht 0,1, frische Lehrer-Demos und Online-DAgger: Der Löser zeigt ab den Fehlerstellen des Bots, wie es weitergeht, nur auf generierten Leveln | A und B zusammen, dazu PLR, 24–30 H-Level und ein Editor |
| Vorbereitung | etwa 1 Arbeitstag | etwa 1 Arbeitstag | 3–4 Tage plus deine Zeit für Level |
| CPU | pro Entscheidung etwa 30 Kern-Stunden | zusätzlich 8–9 h auf 4 Kernen für die Demos | mehrere Tage bis Wochen |
| Erwartete Wirkung | trifft den Ziel-Abschnitt (realistisch +3 bis +8 von 64), hoehle und die Gegner-Fehler | seltene Situationen werden schneller gelernt | höchste Obergrenze |
| Risiko | gering bis mittel | mittel bis hoch: Nachahmen hat in Phase 6 schon geschadet, der Lehrer spielt extrem knapp, und er hilft nur bei Situationen, die der Generator überhaupt baut | Wirkungen lassen sich kaum zuordnen |

\*Fähigkeits-Proben: je 40 feste, generierte Level pro Fähigkeit, gemessen bei jedem Meilenstein. Fähigkeiten sind etwa Truhe vor Leere, Steine auf Reihe 2, Gegner auf der Treppe und Gabelung mit Köder. Diese Proben schwanken weniger als die Prüfung und verbrauchen sie nicht.

**Parallel dazu die Testlevel H:**
- Du baust zuerst 3–4 Pilot-Level im Texteditor wie 2023: ein kurzes, ein mittleres, eins im Stil der Prüfung. Spielen kannst du sie mit `python game.py <level>`.
- Dein aufgezeichneter Durchlauf gibt dem Löser Wegpunkte. Das ist nötig, weil du Tasten kombinieren kannst, die der Bot nicht hat.
- Danach 10–15 Level, langfristig 24–30. Davon sollen mindestens zwei Drittel von Menschen stammen.
- Alle werden vor dem Trainingsstart gesperrt, und du losst sie selbst in die Gruppen.

**Nichts geht verloren:** Wir setzen einen git-Tag und kopieren die wichtigen Modelle nach `models/phase7_*`. `runs/phase7*` bleibt unverändert, und neue Datensätze bekommen neue Namen.

## 7. Was mit Lauf D passiert

D läuft weiter. Weil v8 nicht ankommt, ist D in Wahrheit Lauf C, weitergeführt ab EMA 36M. D beantwortet also, ob die Drift weitergeht. Der Endstand von D ist nach dem Nachmessen ein Kandidat für den Startpunkt von Phase 8.

**Wann wir urteilen:** bei etwa 41–42 Mio. Schritten. Dann vergleichen wir das Mittel der EMA-Meilensteine mit dem von Lauf C über denselben Abschnitt (35,8 von 64 auf der Prüfung, 60,2 von 96 auf der Test-Serie). Erst ein Unterschied ab etwa 6 Siegen gilt als echt.

**Deine Entscheidung:**
- **Automatisches Ende:** Ab etwa 42 Mio. Schritten (grob 17–18 Uhr UTC) kann der Autopilot D als „3. Plateau“ stoppen und die ganze Phase von selbst beenden. Das passiert nicht, wenn die Validierung bis dahin mindestens 192 erreicht oder die Prüfung mindestens 41. Verloren ginge nichts. Ich empfehle trotzdem, diese automatische Abschaltung zu entschärfen.
- **Kerne:** Entweder begrenzen wir D auf die Kerne 0–2, dann wird es etwa 20 % langsamer. Oder wir nehmen hin, dass die Proben auf Kern 3 D etwas bremsen.