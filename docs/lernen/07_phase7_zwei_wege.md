# Lerntagebuch 7 – Phase 7: Zwei Wege und ein unsichtbarer Fehler

Rohdaten: `docs/lernen/daten/phase7_meilensteine.json` (Läufe A–D, jeder Meilenstein roh und als EMA),
`phase7_endauswertung.json`. Nachbetrachtung: `docs/reflexion/phase7_reflexion.md` und `phase7_gegenpruefung.md`.

## Ausgangslage

Phase 6 brachte die ersten Prüfungssiege: 37 von 128 Versuchen, Test-Serie 126 von 192. Für Phase 7 stand
das Ziel vorher fest: **Prüfung ≥ 64/128 (50 %) und Test-Serie ≥ 144/192 (75 %)**. Offene Frage: Reicht das
bisherige Netz, oder braucht der Bot ein anderes?

## Was neu ist

| Baustein | Idee |
|---|---|
| **Zwei Läufe** | **A** trainiert das Phase-6-Netz ab 28 Mio. Schritten weiter. **B** ist ein neues, tieferes Netz (*IMPALA*, 2018 von DeepMind für Reinforcement Learning vorgestellt) mit eigenem Netz für die Value-Schätzung; es ahmt zuerst den Löser nach. Vergleich nach 12 h. |
| **Generator v4, Stufe 12** | Nur noch Sprünge, die der Löser als robust gemessen hat; neue Stufe 12 mit langen Sprungfolgen und Gegnern am Start; eingefrorene Validierung v4 (40 Level). |
| **Rückspul-Starts** | Nach einem Fehlschlag beginnt die nächste Episode manchmal kurz vor der Todesstelle. |
| **EMA-Gewichte** | Neben dem normalen Netz („roh“) wird ein gleitender Mittelwert seiner Gewichte gespeichert (*Exponential Moving Average*); er glättet das Hin und Her der PPO-Updates. |
| **exam2** | Ein zweites, geheimes Prüfungslevel: vom Löser als schaffbar bewiesen, nie analysiert. Es läuft bei jedem Meilenstein mit (32 Versuche), diese Zahlen werden aber weder ausgewertet noch zur Auswahl benutzt; berichtet wird nur der Endwert. Gespeichert wird nur die Zahl der Siege. |
| **Autopilot** | Skript mit festen Regeln: Vergleich nach 12 h, „Plateau-Leiter“ (1. fehlende Muster ergänzen – das meldet der Autopilot nur, umsetzen muss Claude; 2. ruhiger Feinschliff; 3. Lauf beenden), feste Auswahlregel für das Endmodell. |

Begriffe: Ein **Plateau** heißt, über mehrere Meilensteine kommt kein neuer Bestwert. Ein **Abzweig** (*Fork*)
ist ein neuer Lauf, der von einem gespeicherten Stand eines anderen Laufs startet; der alte bleibt erhalten.
Gemessen wird viermal verschieden: **Validierung** = 200 generierte Level, nie trainiert, aber aus derselben
Generator-Welt. **Test-Serie** = 6 von Claude gebaute Level, nie trainiert, aber für Fehleranalyse (v8) und
Modellwahl benutzt. **Prüfung** = Leons Level von 2023 (dazu eine in Phase 2 entschärfte Fassung mit 4 statt
12 Startgegnern), nie trainiert, aber für Fehleranalyse und Modellwahl benutzt. **exam2** = nie analysiert, nie
zur Auswahl benutzt.

## Training

Jeder Meilenstein (alle 1 Mio. Schritte) misst Validierung (von 200), Test-Serie (16 Versuche je Level, von 96)
und Prüfung (64 Versuche je Version). In der Tabelle stehen EMA-Werte, wo nicht anders vermerkt.

| Lauf | Start | Schritte | Prüfung (von 64) | Test-Serie (von 96) | Validierung (von 200) |
|---|---|---|---|---|---|
| A | Phase-6-Netz | 28 → 62 Mio. | 21 (roh, Start) → **43** (34 Mio.) → 1 (Ende) | 55–74 | 171 (roh) → **200** (61 Mio.) |
| B | IMPALA, Nachahmen | 0 → 5 Mio. | immer 0 | höchstens 42 | 142 |
| C | Abzweig von A, EMA 34 Mio. | 34 → 39 Mio. | 42, **43**, 35, 28, 31 | 58–63 | 183–191 |
| D | Abzweig von C, EMA 36 Mio. | 36 → 42 Mio. | Start nachgemessen 31, dann 27–38 | 53–68 | 185–190 |

## Wendungen und Fehlersuche

1. **B war zu langsam.** A schaffte etwa 430 Schritte pro Sekunde, B nur 115 – das neue Netz war drei- bis
   fünfmal teurer als vorher gemessen. Den ersten Nachahm-Versuch verdarb ein Fehler im neuen Netz, den zweiten
   ein Container-Neustart. Nach 12 h stand es A 26 % Prüfung / 64 % Test-Serie gegen B 0 % / 36 %. B wurde
   pausiert, A bekam alle vier Kerne.
2. **A stieg – und driftete.** Zwischen 31 und 36 Mio. Schritten gewann die A-EMA 35–43 von 64 (entschärft bis
   49). Ab 37 Mio. fiel sie und erholte sich bei 39–43 Mio. nur kurz auf 18–28; von 48 bis 62 Mio. lag sie nur
   noch bei 1–11. Gleichzeitig stieg die Validierung auf 200 von 200. *Drift* heißt: An Stellen, für die das
   Training kein Signal liefert, verändert sich das Verhalten ungesteuert mit jedem Update.
3. **Plateau-Regel und Claude griffen ein.** Die Plateau-Regel meldete Stufe 1 („fehlende Muster ergänzen“);
   Claude baute daraufhin Generator v5 (Stufe 12: mehr freie Gegner, weiteste Sprünge dreimal so oft). Claudes
   Fehlerkatalog **der Prüfung** zeigte dann: 17 von 27 Fehlversuchen sprangen über die Truhe hinaus ins Leere –
   also baute Claude Generator v6 (Stufe 12: Truhe in jedem vierten Level auf der letzten Bodenkachel). Neun
   Minuten später kam Stufe 2: Feinschliff mit kleiner Lernrate (3e-5) und ohne Zufallsbonus (*Entropie-Bonus*,
   er belohnt das Ausprobieren). Der Abfall hatte aber schon bei 37 Mio. begonnen, über zwei Stunden *vor* der
   ersten Änderung.
4. **Leons Entscheidungen.** „Ja, ab 34“: Lauf C zweigte von der A-EMA bei 34 Mio. ab, mit Generator v7 (Truhe
   am Rand auch in Stufe 10–11; die zusätzlichen Gegner aus v5 wieder zurückgenommen), Lernrate 3e-5,
   Zufallsbonus 0,003. C hielt zwei Meilensteine lang 42/43 und fiel dann auf 28–35. „Muster ergänzen ab EMA 36“:
   Lauf D zweigte von C bei 36 Mio. ab, mit Generator v8 (Gegner auf Rampen, mehr obere Wege). Die Nachmessung
   genau dieses Stands ergab 31 statt 43. Im Mittel lag D bei 31,0 von 64, C bei 35,8 – ein Unterschied, der im
   Rauschen liegt.
5. **Der unsichtbare Fehler.** Die Reflexion fand: **v5 bis v8 kamen nie im Training an.** Hat eine Stufe
   mindestens 100 gespeicherte, vom Löser geprüfte Level, spielt das Training nur diese (`curriculum.py`). Für
   die Stufen 10–12 lagen 1.779 solcher Level bereit – alle aus Generator v4. Wirklich geändert haben sich also
   nur der ruhige Feinschliff von A (Lernrate 3e-5, kein Zufallsbonus) und bei den Abzweigen der Rücksprung auf
   ältere Gewichte; C lief dazu mit kleinem Zufallsbonus (0,003). D unterschied sich von C nur durch v8, war also
   in Wahrheit C, ab EMA 36 Mio. weitergeführt.
   Dazu kommt eine unsichtbare Wand: In allen Trainingsleveln endet das Level 1–2 Kacheln hinter der Truhe; dort
   hält der Spielcode die Figur fest (`entities.py`), und der Bot sieht den Rand sogar als festen Block. Auf der
   Prüfung folgen hinter der Truhe noch 223 leere Spalten über dem Abgrund. Im Training kann man daher nie hinter
   die Truhe ins Leere springen, auf der Prüfung schon.
6. **Das Ende kam automatisch.** Bei 42 Mio. Schritten stoppte der Autopilot D als „3. Plateau“, damit endete die
   Phase am 2. Oktober um 17:31 Uhr UTC (19:31 Uhr deutscher Zeit). Die Reflexion hatte das vorhergesagt und
   empfohlen, die Abschaltung zu entschärfen; das geschah nicht. (Belegt ist der Stopp durch die Datei
   `runs/phase7d/STOP` von 17:26 Uhr UTC. In `state.json` fehlt der Protokolleintrag dazu, der Zähler steht dort
   bei 2 – vermutlich hat ein zweiter, gleichzeitiger Autopilot-Durchlauf den Stand überschrieben.)

## Endergebnis

Die vorab (30. September) festgelegte Regel wählte zuerst den Lauf mit dem besten Schnitt aus Prüfung +
Test-Serie über seine letzten drei Meilensteine (C) und darin den Stand mit dem besten Dreier-Fenster:
**C, EMA 35 Mio.** Gemessen mit 128 frischen Versuchen je Prüfungsversion und 32 je Test-Serien-Level:

| Messung | Ziel | Phase 6 (28 Mio.) | **Phase 7 (C, EMA 35 Mio.)** |
|---|---|---|---|
| Prüfung original | ≥ 64/128 | 37 | **85 (66 %) – erreicht** |
| Prüfung entschärft | – | 40 | 83 (65 %) |
| Test-Serie | ≥ 144/192 | 126 | **138 (72 %) – um 6 verfehlt** |
| Validierung v2 / v3 / v4 (von 120 / 40 / 40) | – | 114 / 36 / 21 | 114 / 38 / 31 |
| exam2 (geheim) | – | – | **49/128 (38 %)** |

In der Test-Serie: parcours 31, zwei_wege 29, berg 26, festung 25, lange_reise 18, hoehle 9 (je von 32).

Ehrlich eingeordnet:

- Das Ziel ist nur zur Hälfte erreicht. Deshalb gibt es **keinen Merge nach `main`**.
- Die 85 sind leicht optimistisch: Die Prüfung steuerte Fehleranalyse und Modellwahl.
- **exam2 ist die ehrlichste Zahl**, denn das Modell wurde ohne exam2 ausgewählt. Woher der Abstand (85 gegen 49)
  kommt – einfach ein anderes Level oder eine „abgenutzte“ Prüfung –, wissen wir nicht.

## Lektionen

1. **Prüfen, ob eine Änderung im Training ankommt.** Eine Kontrolle, ob die neuen Bausteine in den
   Trainings-Episoden auftauchen, hätte den Pool-Fehler früh gezeigt. So gingen vier Generator-Versionen ins Leere.
   Den Pool-Fehler hatte Claude selbst am 30. September eingebaut: Das Training spielt gespeicherte Level-Texte,
   damit sich geprüfte Level nicht verändern. Dass dadurch neue Generator-Versionen nie ankommen, hat Claude
   übersehen.
2. **Eine falsche Erklärung ist teurer als keine.** Claude als Koordinator schrieb die Einbrüche von A den
   Änderungen v5 und v6 zu („jede Datenänderung senkt die Prüfung erst“). Falsch: Die Daten änderten sich nie,
   und der Abfall begann vorher. Weitere Fehler des Koordinators: Die Lernrate klang kaum ab (nach 62 Mio. noch
   92 % des Startwerts), und A, C und D liefen entgegen der Projektregel auf allen vier Kernen.
3. **Messrauschen ist groß.** 64 Versuche schwanken um ±4 Siege; zwei Einzelmessungen unterscheiden sich erst
   ab etwa 10 Siegen wirklich. Viele „Bestwerte“ und „Einbrüche“ waren Zufall.
4. **Wer am Höchstwert auswählt, wählt Glück.** C-EMA 36 Mio. lag bei der Messung, nach der abgezweigt wurde, bei
   43; dieselben Gewichte ergaben beim Start von D 31. Ehrlich geschätzt liegt der Stand bei etwa 37. Die
   Reflexion schlägt vor, vor jedem Abzweig mit 256 Versuchen nachzumessen.
5. **Perfekt in der Generator-Welt heißt nicht gut in der echten.** A-EMA 61 Mio.: 200/200 in der Validierung,
   7/64 auf der Prüfung. Über die Meilensteine von A laufen beide Werte sogar auseinander: Die Validierung steigt,
   die Prüfung fällt. (Die Korrelation r misst, ob zwei Werte gemeinsam steigen: +1 = immer gemeinsam, 0 = kein
   Zusammenhang, −1 = immer gegenläufig. Roh-Stände von A ab 29 Mio.: r = −0,12, EMA-Stände: r = −0,52.) Die
   Prüfung verlangt, was im Training fehlt: Leere hinter der Truhe, Steine sehr weit oben (Reihe 2, von oben ab 0
   gezählt; im Training liegt nie etwas höher als Reihe 3), Start in der Luft.
6. **Ein Test nutzt sich ab.** Wer eine Prüfung oft analysiert und nach ihr auswählt, misst mit ihr immer weniger
   Verallgemeinerung. Dafür gibt es exam2.
7. **Automatische Regeln brauchen Bremsen.** Fünf Eingriffe in 18 h, zwei davon neun Minuten auseinander. Die
   Status-Auswertung leitete „Rückschritt“ nur aus der Validierung ab und übersah den Prüfungs-Einbruch.
8. **Die Umgebung gehört zum Experiment.** Der Container wird abgeräumt, sobald die Sitzung untätig ist – auch
   wenn sie nur auf eine Freigabe-Anfrage wartet (etwa für `send_later`). Dann sterben die Trainingsprozesse.
   Seit Leons Änderung an CLAUDE.md am 1. Oktober: weiter Beobachtungsrunden von ~9,5 Minuten, aber keine
   nachfragenden Werkzeuge mehr; statt Check-ins per `send_later` eine stündliche Wächter-Routine; kommt nach
   einem Neustart der Planmodus zurück, wird der freigegebene Plan nicht neu aufgerollt.
9. **Ein anderes Netz hilft nur, wenn das Netz der Engpass ist.** Das alte Netz schafft 200/200; B hatte etwa
   gleich viele Gewichte (rund 0,85 Mio.) und war vor allem langsamer. B startete zudem bei 0 Schritten (nur durch
   Nachahmen vorbereitet), A mit 28 Mio. Schritten Vorsprung – fair war der Vergleich nicht.

## Ausblick Phase 8

Die Reflexion (`docs/reflexion/phase7_reflexion.md`) schlägt vor: zuerst billige Proben (etwa Wand statt Leere
hinter der Prüfungs-Truhe), dann den Datenweg reparieren und Level beim Laden abwandeln (Leere hinter der Truhe,
angehobene Level, Start in der Luft, zufälliges Gegnerverhalten), jeden Eingriff gegen einen Kontroll-Ableger
testen – und vor allem ehrlicher messen, mit mehr unabhängigen Testleveln, am besten von Leon gebaut.
