# Lerntagebuch 9 – Phase 9: Umkehren, Kanäle und Mario-Bausteine

Rohdaten: `docs/lernen/daten/phase9_meilensteine.json` (sechs Läufe `phase9_r{1,2,3}_{neu,kontrolle}`, jeder
Meilenstein roh, als EMA und als zweites EMA) und `phase9_endauswertung.json` (Endauswertung, Ausgangsmessung des
Phase-8-Modells, Runden, Autopilot-Protokoll). Regeln: `jumpnrun/rl/autopilot9.py`.

## Ausgangslage

Phase 8 hat das Ziel erreicht und liegt auf `main`. Die größte Schwäche blieb die **Wegwahl**: Auf den
Entwicklungs-Leveln „doppelgabel“ und „lange_tour“ endeten 16 von 16 Versuchen an der Wand am Ende einer oberen
Sackgassen-Straße. Der Bot drehte nie um. Drei Ursachen:

1. Die Belohnung zählte nur einen neuen Rekord nach rechts. Umkehren oder Herunterspringen brachte nichts.
2. Bei der Köder-Gabel aus Generator v9 lag genau unter dem Straßenende ein Loch. Der Bot lernte daraus: „dort
   nie runter“.
3. Der Bot sah nach hinten nur 5 Kacheln.

Leon entschied am 3. Oktober:

- **Schwerpunkte:** Gabelungen und Umkehren, Kanal-/Serpentinen-Level, Mario-inspirierte Bausteine und mehr
  Augmentierung. Für jede Neuerung soll sichtbar sein, **ob sie wirklich hilft** (Kontroll-Arme).
- **Belohnung:** Weg-Distanz zur Truhe.
- **Weiter 13 Reihen.**
- **Claude baut die neuen Testlevel.**
- **Merge-Kriterium:**
  - Auf den neuen versiegelten Leveln mindestens 15 Prozentpunkte besser als das Phase-8-Modell, ohne
    Überlappung der 95-%-Intervalle.
  - Auf der Phase-8-versiegelten Gruppe weiterhin eine untere Grenze von mindestens 50 %.
- **Budget:** höchstens 48 h.

## Was neu ist

| Baustein | Idee |
|---|---|
| **Weg-Distanz-Karte** (`levelgen/distmap.py`) | Für jede Stehfläche die Länge des Wegs zur Truhe. Kanten im Graphen: Laufen, Fallen, Treppenstufen und die einmal gemessenen Sprünge. Berechnet wird rückwärts von der Truhe aus (Dijkstra). Auf einer Sackgasse wächst die Distanz, beim Umkehren schrumpft sie. Rechenzeit ~10 ms je Level. Gegen 500 Löser-Lösungen geprüft: Die Distanz fiel bis auf 3 kleine Ausreißer überall. |
| **Weg-Belohnung** | Erst als „neuer Bestwert“ (`--path-reward`). Ab Runde 2 *potential-basiert* (`--path-delta`): Jede Kachel näher an die Truhe gibt +0,1, jede Kachel weiter weg −0,1, Schleifen heben sich auf. Die Karte ist nur Trainingssignal, der Bot sieht sie nicht. |
| **7. Aktion „links+springen“** | Beim Spiegeln fiel auf: Der Bot hatte nur „rechts+springen“. Nach links konnte er nur senkrecht springen und in der Luft lenken, breite Sprünge nach links waren unmöglich. Gespiegelte Level waren ohne die neue Aktion für den Löser unlösbar, mit ihr lösbar. |
| **Sicht v3** | Raster 13 statt 5 Kacheln nach hinten, Übersicht 40 statt 8 Kacheln zurück, ein „Kompass“ zur Truhe (Richtung, Abstand). Per Netz-Chirurgie übernommen: neue Gewichte starten bei 0, die alte Leistung blieb fast gleich (Prüfung 22 statt 23 von 32). |
| **Generator v10** | Reparierte Gabel mit drei Varianten (unten richtig / umkehren / oben richtig), Kanäle (rechts → Treppe → links → Treppe → rechts, oder Truhe links am Kanal-Ende), Mario-inspirierte Röhren, Block-Pyramiden, Ziegelbrücken, Gegnergruppen. Neue Stufe 13 mischt alles. |
| **Augmentierung v2** | Spiegeln (Truhe links), Gegnerdichte ×0,5–2, Rauschen (Lücken, Plattformhöhen), zwei Level aneinander. Jedes Ergebnis wird mit der Distanzkarte geprüft; unerreichbare Level fallen weg (1 von 150 nach den Korrekturen). |
| **12 neue Level** (`levels/handmade9`) | Je 3 aus Gabel, Kanal, Mario-inspiriert und lang/gespiegelt, alle vom Löser bewiesen. Festes Los (Seed 20261003) in 4 Entwicklungs-, 4 Test- und 4 versiegelte Level. |
| **Messsystem** | Wie Phase 8, die Entwicklungsgruppe hat nun 15 Level. Das Dev-Mittel wird zusätzlich getrennt als „alt“ (11 Phase-8-Level) und „neu“ (4 Phase-9-Level) ausgewiesen. Dazu 6 neue Fähigkeits-Proben (umkehren, kanal, truhe_links, mario, lang, gegner_dicht). |

**Ausgangsmessung des Phase-8-Modells** auf den neuen Gruppen:

- Dev-Mittel 49,5 %: alte Level 67,5 %, neue Level **0 %**
- Proben „kanal“ und „truhe_links“: 0/20
- Probe „umkehren“: 10/20

Die Proben „mario“, „lang“ und „gegner_dicht“ löste schon das Phase-8-Modell zu 20/20. Diese drei Proben
unterscheiden darum kaum etwas – ein Fehler im Probenbau, der in der nächsten Phase behoben werden sollte.

## Die drei Runden

| Runde | Start (Dev-Mittel) | Was „neu“ zusätzlich bekam | neu | Kontrolle | Sieger |
|---|---|---|---|---|---|
| 1 | Phase-8-Endmodell (49,6 %) | Weg-Belohnung (Bestwert) + Sicht v3 + 7 Aktionen + reparierte Gabel | 48,7 % | 48,0 % | Kontrolle (< +3 Pp) |
| 2 | Runde-1-Kontrolle, EMA 59 Mio. (45,4 %) | dazu potential-basierte Weg-Belohnung + Generator v10 (Kanäle, Mario, Stufe 13) | **45,5 %** | 41,8 % | neu |
| 3 | Runde-2-neu, EMA 65 Mio. (45,9 %) | Augmentierung v2; **beide** Arme lernen zusätzlich von Lehrer-Beispielen mit links+springen | 41,5 % | **45,1 %** | Kontrolle |

Was in den Runden passierte:

- **Runde 1:** „Neu“ wurde auf den alten Leveln etwas besser. Beim Umkehren tat sich nichts: Die Probe blieb bei
  9–10 von 20, auf den neuen Dev-Leveln blieb es auf beiden Armen bei 0 %. Die Bestwert-Belohnung bestraft das
  Betreten einer Sackgasse nicht. Wer umkehrt, bekommt lange nichts.
- **Runde 2:** Die potential-basierte Belohnung kam als vorab angekündigte Regel dazu. Bedingung war, dass
  „umkehren“ bei ≤ 10/20 blieb. Damit prüfte Runde 2 ein **Paket** aus Signal und Leveln, nicht jeden Teil
  einzeln.
  - „Neu“ gewann das Level gabel_drei teilweise (6 von 16).
  - Von über 600 Kanal- und Umkehr-Episoden im Training gewann es keine einzige.
  - Ursache war ein **Erkundungsproblem**: Nach 59 Mio. Schritten „nach rechts“ wählte der Bot „links“ fast nie.
    Die neue Aktion „links+springen“ kam in 400 Schritten kein einziges Mal vor. Sie war mit Absicht
    ~50-mal unwahrscheinlicher als „links“ gestartet, damit die Netz-Chirurgie das Verhalten nicht verändert.
- **Runde 3:** Der Löser erzeugte 283 Lehrer-Beispiele mit 1042 Mal „links+springen“: Kanäle, Kanal-Enden,
  Spiegel und Starts direkt an einer Sackgasse. Sie wurden 6-fach gewichtet als Imitations-Verlust und als
  Startpunkte genutzt, und zwar in **beiden** Armen. So unterschied sich Runde 3 weiterhin nur in der
  Augmentierung.
  - Im Training gewann die Kontrolle erstmals Kanal-Enden: 69 von 261.
  - Auf den neuen Dev-Leveln erreichte sie bis 12,5 %.
  - Die Augmentierung v2 kostete dagegen 3–4 Prozentpunkte.

Eine Unschärfe gab es: „Neu“ trainierte in Runde 1 und 2 wegen der breiteren Sicht ~30 % langsamer. Geurteilt
wurde bei je 6 Mio. Schritten des jeweiligen Arms, die Kontrolle war da schon 1–2 Mio. weiter. Weil die Kontrolle
mit mehr Schritten eher schlechter wurde, hat das „neu“ nicht benachteiligt.

## Endergebnis

Endmodell nach fester Regel (bestes Fenster aus 3 Meilensteinen, über alle Arme): **EMA2 aus Runde 1 „neu“, 55 Mio.
Schritte** (Dev-Fenster 52,2 %). Danach wurde einmal versiegelt ausgewertet (4. Oktober, 13:32–13:36 UTC):

| | Phase-8-Modell | Phase-9-Endmodell |
|---|---|---|
| Prüfung (256 Versuche) | 183 | **191** |
| Dev-Mittel (15 Level) | 49,5 % | 49,4 % |
| neue versiegelte Level (4 × 32) | 32/128 | 32/128 → **+0 Pp** |
| Phase-8-versiegelt (exam2 128 + 4 × 32) | **208/256 (81 %)** | 156/256 (61 %, untere Grenze 54,8 %) |

**Merge-Kriterium nicht erfüllt** – `main` bleibt auf dem Phase-8-Stand.

Das Phase-9-Endmodell ist auf der Prüfung und auf den Entwicklungs-Leveln mindestens gleich gut wie Phase 8. Auf
den ungesehenen Phase-8-Leveln (versiegelt) ist es aber **20 Prozentpunkte schlechter**. Die Auswahl nach dem
Dev-Mittel hat also auf die Entwicklungs-Level hin überangepasst, und erst die versiegelte Gruppe hat das gezeigt.

## Fehler und Korrekturen unterwegs

- Die Distanzkarte kannte zuerst keine **direkten Treppenstufen**. Kanäle wirkten dadurch unerreichbar. Ergänzt
  wurde die Kante „eine Stufe hoch“.
- Die Augmentierung **„Leere hinter der Truhe“ zerstörte Kanal-Enden**, weil sie alles rechts von der Truhe
  abschnitt. Sie greift jetzt nur, wenn rechts nichts mehr kommt.
- Bei **„Start in der Luft“** fand die Karte den Startpunkt nicht. Jetzt gilt die Landestelle darunter.
- Das Level **„turm“ war mit Gegnern in geschlossenen Gängen** für den Löser nicht beweisbar. Es wurde zu einem
  reinen Wegfindungs-Level ohne Gegner.
- Die **Aufbereitung der Lehrer-Beispiele kannte nur 6 Aktionen** und wäre an „links+springen“ gescheitert.
  Korrigiert, dazu ein Test.
- Die **Lehrer-Beispiele bremsten das Training** spürbar, weil sie auf denselben Kernen liefen. Sie wurden bei
  283 Leveln gestoppt.

## Lektionen

1. **Das Interface begrenzt, was lernbar ist.** Ohne „links+springen“ sind manche Level schlicht unmöglich. Das
   fiel erst beim Spiegeln auf, nach acht Phasen.
2. **Eine Belohnung hilft nur bei Dingen, die der Bot auch ausprobiert.** Nach langem Rechts-Training probiert er
   „links“ praktisch nie. Weder die Weg-Belohnung noch neue Level änderten das. Erst Vorbilder (Lehrer-Beispiele)
   brachten die ersten Erfolge.
3. **Mehr Augmentierung ist nicht automatisch besser.** In Phase 8 half sie stark, hier schadete sie. Der Grund:
   Spiegeln verlangt eine Fähigkeit (nach links laufen), die noch fehlte. Dann ist es vor allem Rauschen.
4. **Weitertrainieren kostet alte Fähigkeiten.** Beide Arme verloren in Phase 9 auf den alten Leveln, die
   Kontrollen sogar ohne jede Neuerung.
5. **Die versiegelte Gruppe ist unverzichtbar.** Auf den Entwicklungs-Leveln sah das Endmodell gleich gut aus,
   versiegelt war es klar schlechter.

## Ausblick Phase 10 (zur Entscheidung)

- **Curriculum statt Mischung:** erst kurze Level, auf denen nur Umkehren oder Kanäle geübt werden, mit vielen
  Lehrer-Beispielen. Danach schrittweise mischen.
- **Gezielt mehr ausprobieren:** einen Zufallsbonus (Entropie) nur für die Links-Aktionen, oder „links+springen“
  gleich wahrscheinlich wie „links“ starten.
- **Schutz vor Vergessen:** Phase-8-Level fest einmischen, eine kleinere Lernrate oder ein Abstandsterm zum
  Phase-8-Netz.
- **Auswahl robuster machen:** das Endmodell zusätzlich am Schutz- und Test-Wert messen, nicht nur am Dev-Mittel.
- **Proben verbessern:** „mario“, „lang“ und „gegner_dicht“ schwerer machen, damit sie etwas unterscheiden.
