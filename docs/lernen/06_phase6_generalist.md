# Lerntagebuch 6 – Phase 6: Weiter sehen, länger üben

Interaktive Version: `docs/lernen/seiten/phase6.html` (Video `phase6_pruefung_28mio.mp4` im selben Ordner).
Rohdaten: `docs/lernen/daten/phase6_meilensteine.json` (alle 1 Mio. Schritte), `phase6_endauswertung.json`.

## Ausgangslage

Phase 5 schaffte 114/120 unbekannte Level, aber 0 von 32 Versuchen auf dem Prüfungslevel von 2023.
Die Versuche scheiterten an vier Stellen: Gegnerregen am Start, eine Sackgasse unten, deren Ende erst
~60 Kacheln später sichtbar wird, lange Trittsteinketten und eine Gegner-Senke oben.

## Was neu ist

| Baustein | Idee |
|---|---|
| **Übersichtskarte** | Zweites, grobes Bild: 32 Spalten à 4 Kacheln, von 8 Kacheln hinter bis 120 vor dem Bot (Block-Anteil, Stehfläche, Gegner, Truhe). Damit sieht der Bot das Ende einer Sackgasse, bevor er hineinläuft. |
| **Netz-Chirurgie** | Das Phase-5-Netz bekommt einen dritten Eingangszweig. Dessen letzte Schicht startet mit lauter Nullen – das neue Netz verhält sich am Anfang *exakt* wie Phase 5 (getestet: Abweichung 0,0) und lernt erst nach und nach, die Karte zu nutzen. |
| **Generator v3** | Neue Stufen 10 (~220 Kacheln) und 11 (~320) mit Prüfungs-Mustern: Gegnerregen über schwebender Treppe, Sackgasse 40–80 Kacheln, lange Steinketten mit Höhenwechsel, Gegner-Graben auf hohem Plateau. Der Generator liefert Wegpunkte mit, damit der Löser lange Level in Etappen lösen kann. |
| **Test-Serie** | 6 handgebaute schwere Level (Berg, Höhle, Festung, Parcours, Zwei Wege, Lange Reise, bis 310 Kacheln), alle vom Löser bewiesen, nie trainiert. |
| **Zufällige Startpunkte** | 30 % der Episoden beginnen an einer zufälligen Stelle eines Musterlaufs des Lösers. So übt der Bot die späten, schweren Abschnitte langer Level viel öfter, statt immer wieder von vorn zu beginnen. Diese Episoden zählen nicht für das Curriculum. |
| **Eingefrorene Validierung** | Validierung v2 (120 Level, Stufen 4–9) und v3 (40 Level, Stufen 10–11) liegen als Text in `levels/validierung/` – so bleiben Modelle vergleichbar, auch wenn sich der Generator ändert. |

## Training

PPO mit Vorbild-Bremse wie in Phase 5, 16 Stunden (31,9 Mio. Schritte), alle Stufen 0–11 frei.
Alle 1 Mio. Schritte eine Meilenstein-Auswertung auf einem eigenen CPU-Kern: Validierung v2+v3,
Test-Serie (16 Versuche je Level), Prüfung (32 Versuche je Version) mit Auswertung, **wo** die Versuche enden.

Überraschung beim Start: Das Nachahmen nur für den neuen Zweig machte den Bot schlechter
(86 % → 42 % Validierung, obwohl die Übereinstimmung mit dem Löser stieg). Das Skript behielt deshalb
die alten Gewichte; der Bot musste die Karte allein durch PPO nutzen lernen.

## Die Fehlersuche während des Trainings

Die „Wo enden die Versuche“-Statistik war das wichtigste Werkzeug. Dreimal zeigte sie ein Muster,
das in den Trainingsleveln fehlte – und dreimal half es, genau dieses Muster nachzurüsten
(nur für Stufen 10/11, die eingefrorene Validierung blieb unverändert):

1. **Tiefsprung (16 Mio.):** 22 von 64 Versuchen starben bei Kachel 259 – Sprung von einer hohen Plattform
   über 4 Kacheln auf den 8 Reihen tieferen Boden. Der Generator baute höchstens 4 Reihen tiefe Sprünge.
2. **Truhe ohne Wand (16 Mio.):** 6 Versuche sprangen **über** die Truhe und fielen aus dem Level. In allen
   generierten Leveln stand eine Wand hinter der Truhe – der Bot hatte gelernt, dass die Wand ihn stoppt.
3. **Weiter Sprung nach oben (21 Mio.):** Die eigentliche Todesstelle lag einen Sprung früher: 3 Kacheln weit
   *und* eine Reihe hoch. In steigenden Steinketten gab es bisher nur 1–2 Kacheln Abstand.

Sieben Millionen Schritte nach der letzten Änderung kam der Durchbruch: **8/32 bei Meilenstein 28 Mio.**

## Endergebnis (128 frische Versuche je Prüfungsversion)

| Modell | Validierung v2 | v3 | Test-Serie (von 192) | Prüfung original | entschärft |
|---|---|---|---|---|---|
| Phase 5 | 114 | 17 | 97 | 0 | 0 |
| Phase 6, beste Validierung (30 Mio.) | **116** | 35 | 111 | 4 (3 %) | 4 |
| **Phase 6, 28 Mio.** | 114 | **36** | **126** | **37 (29 %)** | **40 (31 %)** |
| Phase 6, Ende (31,9 Mio.) | 105 | 32 | 120 | 19 (15 %) | 21 |

Ehrlich eingeordnet:

- Das Stopp-Kriterium (≥ 16/32 an zwei Meilensteinen hintereinander) wurde **nicht** erreicht; das Training endete am 16-h-Limit.
- Das 28-Mio.-Modell wurde ausgewählt, **weil** es beim Prüfungs-Meilenstein auffiel. Die 37/128 stammen zwar aus frischen Versuchen, aber die Auswahl selbst war nicht blind – die Zahl ist darum leicht optimistisch.
- Das „saubere“ Modell (nur nach Validierung ausgewählt) schafft 4/128. **Beste Validierung ≠ bestes Prüfungsergebnis** – genau wie in Phase 5.
- Die Prüfungs-Ergebnisse schwanken stark von Meilenstein zu Meilenstein (0 → 8 → 0 von 32). Jedes PPO-Update verschiebt die Strategie ein wenig; bei ~1.300 Entscheidungen hintereinander summieren sich kleine Unterschiede.

## Lektionen

- **Fehleranalyse schlägt Rechenzeit.** Die größten Sprünge kamen nicht durch längeres Training, sondern durch das Nachrüsten der drei fehlenden Muster.
- **Ein Bot lernt die Regeln seiner Trainingswelt – auch die zufälligen.** „Hinter der Truhe steht immer eine Wand“ war nie beabsichtigt, aber der Bot hat es gelernt.
- **Generalisierung braucht Vielfalt in genau den Dimensionen, die im Test vorkommen.** Die Übersichtskarte allein reichte nicht; erst passende Trainingssituationen machten sie nützlich.
- **Lange Aufgaben verstärken kleine Schwächen.** 95 % Erfolg pro Abschnitt heißt bei 8 schweren Abschnitten nur 66 % für das ganze Level.
