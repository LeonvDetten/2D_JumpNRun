# Lerntagebuch 8 – Phase 8: Ehrlich messen

Rohdaten: `docs/lernen/daten/phase8_meilensteine.json` (sechs Läufe `phase8_r{1,2,3}_{neu,kontrolle}`, jeder
Meilenstein roh, als EMA und als zweites EMA), `phase8_endauswertung.json` (Endauswertung, Autopilot-Protokoll,
Runden, billige Proben, Löser-Stichprobe). Regeln: `jumpnrun/rl/autopilot8.py`.

## Ausgangslage

Phase 7 endete mit Prüfung 85/128, Test-Serie 138/192 und der geheimen exam2 bei nur 49/128 – Ziel verfehlt. Die
Reflexion (`docs/reflexion/phase7_reflexion.md`) fand zwei Hauptprobleme: Neue Generator-Versionen kamen nie im
Training an, und unsere Messung war zu schwach, um echte Fortschritte von Zufall zu unterscheiden. Leon entschied
am 2. Oktober:

- **Variante A „Daten-Fokus“**: Datenweg reparieren, Level abwandeln, jeden Eingriff gegen eine Kontrolle testen.
- **Der Abgrund hinter der Truhe gehört zur Prüfung.** Ein Mensch sieht ihn auch – also muss er ins Training.
- **Claude baut die neuen Testlevel.**
- **Merge-Kriterium:** Die untere Grenze des 95-%-Intervalls (nach *Wilson*, eine Formel für Erfolgsquoten) der
  zusammengelegten versiegelten Gruppe muss mindestens 50 % sein. Das Intervall gibt an, wo die wahre Quote mit
  95 % Sicherheit liegt; die untere Grenze ist also eine vorsichtige Schätzung.

## Was neu ist

| Baustein | Idee |
|---|---|
| **Messprotokoll mit vier Gruppen** | **Entwicklung** (Prüfung, Test-Serie, 4 neue Level): darf analysiert und zur Modellwahl benutzt werden. **Test** (4 neue Level): nur Gesamtsiege. **Versiegelt** (exam2 + 4 neue Level): nur einmal ganz am Ende, für das vorab gewählte Modell. **Schutz** (80 generierte Level): Alarm gegen Vergessen. Hauptwert ist das **Dev-Mittel**: die mittlere Erfolgsquote über die 11 Entwicklungs-Level, jedes zählt gleich. |
| **Fähigkeits-Proben** | 7 Fähigkeiten (Truhe vor Abgrund, hohe Steine, Gegner auf der Treppe, Köder-Gabelung, Decke, Start in der Luft, Gegner kommt entgegen) mit je 20 festen, vom Löser bewiesenen Leveln. Sie zeigen, *ob* eine Änderung ankommt, ohne die Prüfung abzunutzen. |
| **12 neue Level** (`levels/handmade8`) | Von Claude Kachel für Kachel gesetzt, nicht aus Generator-Bausteinen; jedes vom Löser bewiesen. Ein festes Los (Seed 20261002) teilte sie je zu viert auf Entwicklung, Test und Versiegelt auf; Prüfsummen verhindern spätere Änderungen. |
| **Datenweg repariert** | `--pool-share 0.4`: Nur noch 40 % der Episoden kommen aus gespeicherten Leveln, der Rest frisch vom Generator. Jede Episode notiert ihre Herkunft. |
| **Level-Augmentierung** | Beim Laden werden 70 % der Trainingslevel zufällig abgewandelt (`--augment 0.7`): Leere hinter der Truhe, um 1–2 Reihen angehoben, feste Decke, Start in der Luft, Gegner mit zufälliger Richtung und Weckabstand (12–24 Kacheln). Löser-Stichprobe: in allen sechs Fällen (ohne, Leere, Decke, Luft, Gegner je 30/30; Anheben 19/19, bei 11 Leveln war kein Platz) blieb jedes Level lösbar. |
| **Generator v9** | Köder-Gabelungen: ein verlockender oberer Weg endet an einer Wand, richtig ist der Boden. |
| **Lernrate und zweites EMA** | Die Lernrate klingt pro Runde in einer Kosinus-Kurve über 8 Mio. Schritte auf 10 % ab. Neben dem EMA gibt es ein zweites, langsameres (*EMA2*). |
| **Runden „neu“ gegen „Kontrolle“** | Beide Arme starten am selben Stand, je 2 Kerne, 6 Mio. Schritte. Vorab festgelegt: „neu“ gewinnt mit ≥ 3 Prozentpunkten mehr Dev-Mittel (Schnitt der letzten drei EMA-Meilensteine), sonst gewinnt die Kontrolle – außer ihr Schutzwert ist um ≥ 5 Level schlechter. Der Sieger ist Start der nächsten Runde. |

## Die billigen Proben

Vor dem Training, nur Auswertung:

1. **Wand statt Abgrund.** Das Phase-7-Modell gewann auf der Original-Prüfung 81 von 128, mit einer Wand hinter
   der Truhe 98. Von den 47 Fehlversuchen endeten 11 genau an der Truhenspalte – der Sprung über die Truhe hinaus.
2. **Weg-Fehler oder Sprung-Fehler?** 124 Versuche nahmen den oberen Weg, nur 3 den unteren. Von den 23 Toden an
   den Trittsteinen lagen 20 auf dem oberen Weg. Die Köder-Vermutung erklärt also nur 3 davon.
3. **Nachmessen mit 256 Versuchen:** A-EMA 34 Mio. 167, C-EMA 35 Mio. 164, C-EMA 36 Mio. 145 (umgerechnet 36 von
   64 statt der damals gemessenen 43). Startpunkt wurde C-EMA 35 Mio. mit dem besten Mittel aus Prüfung und
   Test-Serie (68 %).
4. **Störprobe:** Wiederholt der Bot in 15 % der Schritte stur seine letzte Aktion, sinkt er auf 13 von 128. Er
   spielt also extrem knapp getaktet.

## Die drei Runden

| Runde | Start (Dev-Mittel) | Was „neu“ zusätzlich bekam | neu | Kontrolle | Sieger |
|---|---|---|---|---|---|
| 1 | C-EMA 35 Mio. (50,3 %) | Datenweg 40 % + Augmentierung (Kontrolle: alter Stand) | **59,6 %** | 42,6 % | neu |
| 2 | Runde-1-neu, EMA 41 Mio. (68,3 %) | erweiterte Beobachtung + Festhängen = Tod | 62,6 % | **66,2 %** | Kontrolle |
| 3 | Runde-2-Kontrolle, EMA 47 Mio. (63,2 %) | PLR (Level, an denen der Bot am meisten lernt, öfter spielen) | **68,0 %** | 64,0 % | neu |

Runde 1 war die deutlichste: Bei den Fähigkeits-Proben blieb die Kontrolle bis zuletzt bei 0/20 für Köder und
Decke, „neu“ kam nach 6 Mio. Schritten auf 13/20 und 16/20. Diesmal kamen die Daten also nachweislich im Training
an. Die Schutzwerte (66–79 von 80) lösten nie Alarm aus. Die Phase dauerte vom 2. Oktober, 20:51 Uhr, bis
3. Oktober, 10:51 Uhr UTC.

## Endergebnis

Die feste Regel nahm das beste Fenster aus drei aufeinanderfolgenden Meilensteinen über alle Läufe:
**Runde 3 neu, EMA2 bei 50 Mio. Schritten** (Fenster 69,7 %). Gemessen einmal, mit festen Seeds:

| Messung | Phase 7 (C, EMA 35 Mio.) | **Phase 8 (R3 neu, EMA2 50 Mio.)** |
|---|---|---|
| Prüfung original | 85/128 (66 %) | 183/256 (71 %) |
| Test-Serie | 138/192 | **153/192 (80 %)** |
| Dev-Mittel (11 Level) | 50,3 % (Kurzmessung) | 67,6 % |
| Test-Gruppe (4 neue Level) | – | 90/128 |
| **exam2 (geheim)** | 49/128 (38 %) | **85/128 (66 %)** |
| **Versiegelt gesamt** (exam2 + 4 Level) | – | **208/256 (81 %), Intervall 76–86 %** |

Die untere Grenze liegt bei **76 % ≥ 50 % – Kriterium erfüllt.** Selbst exam2 allein hätte es erfüllt (untere
Grenze 58 %). In der Test-Serie: parcours 32, zwei_wege 31, festung 29, berg 26, lange_reise 18, hoehle 17
(Phase 7: 9). Die versiegelten neuen Level ergaben 123 von 128.

Drei Level blieben bei **0 von 32**: **koeder** (Test), **doppelgabel** und **lange_tour** (Entwicklung). Alle drei
verlangen eine Wegwahl an einer Gabelung, bei der der verlockende Weg in einer Sackgasse endet. doppelgabel kam in
keinem Meilenstein über 2/16, lange_tour nie über 0. Bemerkenswert: Die generierten Köder-Proben schafft der Bot
inzwischen meist (15–19 von 20) – die von Hand gebauten nicht.

## Fehler und Korrekturen unterwegs

- **Modelle ohne Begleitdatei.** Kopierte Phase-7-Modelle hatten keine Begleitdatei mit ihren Einstellungen
  (etwa Aktionswiederholung und Übersichtskarte) und spielten deshalb mit falschen Werten. Behoben durch
  nachgereichte Begleitdateien.
- **Augmentierung zuerst teils unlösbar.** Beim Anheben und bei der Decke war in der ersten Löser-Stichprobe etwa
  ein Viertel der Level unlösbar, weil Sprünge an die Decke oder den oberen Rand stießen. Neue Regel: über dem
  höchsten Gelände bleiben immer zwei Reihen frei. Danach war die Stichprobe vollständig lösbar.
- **Der Abgrund verschwand beim Speichern.** `to_text()` schneidet leere Spalten am Zeilenende ab – an zwei Stellen
  wurde so aus der Leere hinter der Truhe wieder eine Wand. Jetzt werden volle Zeilen gespeichert, ein Test prüft
  das.
- **Runde 3 startete nicht.** `--plr` stand ohne Wert in der Regel; der neue Arm stürzte ab. Korrigiert zu
  `--plr 0.3` nach wenigen Minuten, ein Test prüft jetzt alle Runden-Schalter.
- **Container-Neustart** um 23:59 Uhr in Runde 1: Beide Arme wurden vom Autopiloten am letzten Stand fortgesetzt.
- **Tag nicht hochgeladen.** Das Markieren des Endstands per Git-Tag scheiterte am Proxy.

## Lektionen

1. **Erst messen, dann ändern.** Mit vier Gruppen, festen Seeds und Kontroll-Armen lässt sich erstmals sagen,
   welcher Eingriff etwas bringt: Daten ja, Beobachtung und Festhängen-Strafe nicht (zumindest nicht in 6 Mio.
   Schritten), PLR ein wenig.
2. **Prüfen, ob es ankommt.** Die Fähigkeits-Proben zeigten in Runde 1 sofort, dass Köder und Decke im Training
   angekommen waren – der Phase-7-Fehler wäre so nicht unbemerkt geblieben.
3. **Auch Kurzmessungen rauschen.** Der Startwert von Runde 2 wurde mit 68,3 % gemessen, der Meilenstein derselben
   Gewichte mit 61,2 %. Deshalb urteilt die Regel über drei Meilensteine.
4. **Daten schlagen Netz-Tricks.** Der größte Sprung (+17 Prozentpunkte gegen die Kontrolle) kam allein aus
   besseren Trainingsdaten.
5. **Gelernt ist nicht verallgemeinert.** Generierte Köder werden gelöst, handgebaute Gabelungen nie. Der Bot
   hat ein Muster gelernt, kein Verständnis von „dieser Weg endet in einer Sackgasse“.
6. **Der Bot ist zerbrechlich.** 15 % Störung lassen ihn von 81 auf 13 von 128 fallen.

## Ausblick Phase 9

Der klare Engpass ist die **Wegwahl an Gabelungen**: koeder, doppelgabel und lange_tour stehen bei null. Dafür
braucht es Gabelungen, deren Sackgasse erst spät sichtbar wird, und vielleicht eine bessere Nutzung der
Übersichtskarte. Ebenso wichtig sind **mehr von Menschen gebaute Level**: Drei der vier versiegelten neuen Level
lagen bei 32/32 – vermutlich waren sie zu leicht, weil Claude sie mit demselben Blick gebaut hat wie den Generator.
Die aussagekräftigste Zahl dieser Phase ist deshalb **exam2: 85 von 128**.
