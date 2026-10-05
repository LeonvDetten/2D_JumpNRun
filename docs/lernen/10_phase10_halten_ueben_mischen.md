# Lerntagebuch 10 – Phase 10: Halten, üben, mischen

Rohdaten und Regeln: `docs/lernen/daten/phase10_vorregistrierung.json` (alle Schwellen, vor dem ersten
Trainingsschritt committet), `runs/phase10/state.json` (Autopilot-Protokoll), `jumpnrun/rl/autopilot10.py`,
`autopilot10_bc.py`, `select10.py`. *Entwurf – wird während der Phase ergänzt.*

## Ausgangslage

Phase 9 verfehlte ihr Ziel:
- Auf den neuen versiegelten Leveln gab es keinen Gewinn (32/128 wie Phase 8).
- Auf der Phase-8-versiegelten Gruppe gab es sogar einen Verlust (208 → 156 von 256).
- `main` blieb auf Phase 8.

Die Nachanalyse fand drei Gründe:

1. **Messfehler.**
   - Die Auswertung brach nach 600 Frames ohne neuen *Rechts*-Rekord ab, und das Zeitlimit hing an der Levelbreite.
   - Damit endete selbst die Löser-Lösung von „serpentine“ und „spiegelweg“ als „feststeckend“.
   - Ein Teil der „0 %“ bei den neuen Fähigkeiten war also Messfehler.
2. **Vergessen.**
   - Nach jedem Lernraten-Neustart auf 1e-4 fiel der Wert auf den alten Leveln, in 11 von 12 Runden.
   - Das galt auch für Arme, die nur Phase-8-Level spielten.
3. **Zu wenig Übung.**
   - Kurze Übungssituationen machten nur ≈ 3 % der Schritte aus.
   - „links+springen“ kam in 779 von 300 000 Vorbild-Beispielen vor.

Leon entschied am 4./5. Oktober:
- **Erst üben, dann mischen.**
- **Vergessen verhindern** durch einen festen Phase-8-Anteil (45 → 55 → 60 % der Schritte) und langsameres Lernen.
- **Startmodell:** Phase 8 + Umbau auf die neue Sicht.
- **Runde A** vergleicht 2e-5 mit 5e-5.
- **Anker** nur nach Regel.
- **Lösbarkeit** wird über einen blinden Zähler geprüft, der nur Summen ausgibt.
- **Budget:** 48 h.
- **Kein automatischer Merge:** Leon entscheidet selbst.

## Schritt 0 – die Messung repariert

| Was | Vorher | Jetzt |
|---|---|---|
| Abbruch „feststeckend“ | 600 Frames ohne neuen Rekord nach **rechts** | 600 Frames ohne neuen Bestwert der **Weg-Distanz** zur Truhe |
| Zeitlimit | nach Levelbreite | `max(Breite, 1,2 × Weglänge)` Kacheln × 12 Frames + 200 |

- **Prüfung der Messung selbst:**
  - Alle 15 Löser-Lösungen der Dev-Level gewinnen jetzt im Mess-Env.
  - Der blinde Zähler meldet auch jede Test- und versiegelte Gruppe als voll lösbar; vorher waren es bei
    handmade9-Test und handmade9-versiegelt nur 2 von 4.
- **Verschiebungsprüfung:** Das Phase-8-Modell spielte 352 Episoden mit denselben Seeds nach alter und neuer Regel.
  0 Ergebnisse änderten sich. Die Reparatur verfälscht die alten Werte also nicht.

**Ausgangswerte** (volle Messung, reparierte Regel):

| Modell | dev_alt (11 alte Dev-Level) | Prüfung | Schutz |
|---|---|---|---|
| Phase 8 (3 Messungen gepoolt) | 66,4 % | 44–52 / 64 | 76 / 80 |
| Startmodell (Phase 8 + Umbau, 3×) | 67,7 % | 37–42 / 64 | 71 / 80 |
| Phase-9-Endmodell | 68,3 % | 45 / 64 | – |
| „Delle“ R1-Kontrolle roh 53M | 47,6 % | 3 / 64 | – |

## Neue Bausteine

| Baustein | Idee |
|---|---|
| **Lernraten-Stufen ohne Neustart** | Die Lernrate bleibt je Stufe konstant und sinkt nur. Nach dem Umbau trainiert 0,15 Mio. Schritte nur der Critic, danach steigt die Rate über 0,3 Mio. Schritte an. Eine Bremse kann sie halbieren. |
| **Übungslevel** (`levelgen/skills.py`) | 7 Arten: Kanal-Ende, Kanal mit zwei Kehren, Kanal mit breitem Absprung, Sackgasse runter, Gabel umkehren, Gabel oben, Truhe kurz links. Je 3 Stufen: d0 startet kurz vor der Schlüsselstelle, d2 hat volle Geometrie mit Gegnern. Gezogen wird an der Lerngrenze (p(1−p)); die nächste Stufe öffnet ab 70 % frischen Siegen. |
| **Mischung nach Schritten** (`MixSource`) | Drei Quellen: Phase-8-Level, Übung, lange v10-Level. Neue Episoden kommen aus der Quelle, die ihrem Soll-Anteil an *Schritten* am weitesten hinterherhinkt. So stimmen die Anteile, obwohl Übungsepisoden viel kürzer sind. |
| **Zweiter Vorbild-Strom (BC2)** | Lehrer-Beispiele auf Übungsleveln. „links+springen“ ist auf 5 % der Samples hochgezogen, das Gewicht sinkt von 0,1 über 0,05 auf 0,03. Der alte Strom (Phase-8-Demos, 0,02) bleibt. |
| **Drift-Messung** | KL zum eingefrorenen Phase-8-Modell auf ~6000 alten Zuständen, alle 0,25 Mio. Schritte. Sie dient als Frühwarnung und löst die Bremse aus, ist aber nie ein Urteil. |
| **Wächter-Level** (`levels/handmade10`) | 8 lange Level im Phase-8-Stil, je 2 Generator-Level aneinander (526–701 Kacheln, ähnlich der Prüfung), alle vom Löser bewiesen. 4 Val, 4 Test. **Gültig**: Auf Val gewinnt Phase 8 77 %, die bekannte Delle 50 %. Der Abstand beträgt 27 Pp, verlangt waren 8 Pp. |
| **Anker** (nur nach Regel) | Zug zum Phase-8-Verhalten auf Zuständen gewonnener Phase-8-Episoden, ohne Gabeln und Kanäle. Er lässt 2 % Platz für „links+springen“, und sein Gewicht passt sich an. |
| **Korrektur-Beispiele (DAgger)** (nur Runde C, Fall 2) | Der Bot spielt. Wo er scheitert, übernimmt der Löser 20–40 Schritte vor dem Ende. |

## Ablauf (vorregistriert)

1. **Runde A – wie langsam lernen?** 2e-5 gegen 5e-5, je 4 Mio. Schritte, nur Phase-8-Level.
   - Als sicher gilt eine Lernrate, wenn dev_alt (gepoolt über +2/+3/+4 Mio.) weniger als 3 Pp unter dem
     Startmodell liegt.
2. **Lehrer-Fenster:** 2500 Lehrer-Beispiele, Übungsproben und Anker-Zustände. Dabei läuft kein Training parallel.
3. **Runde B – erst üben, dann mischen** (je 10 Mio.). „neu“ übt zuerst (55 % Übung) und mischt dann; die
   Kontrolle mischt von Anfang an fest. Im Zeitmittel spielen beide dieselben Anteile.
   - **Urteil bei +8/+9/+10 Mio.:** F (½ dev_neu + ½ Fähigkeitsproben) muss um ≥ 5 Pp steigen, Alt darf nicht
     mehr als 3 Pp fallen.
4. **Runde C – Regel-Runde** (je 6 Mio.):
   - bei gerissenem Alt-Tor eine Reparatur;
   - bei zu schwachen Fähigkeiten DAgger;
   - wenn beides gut ist, mehr Mischen.
5. **Auswahl und Endauswertung:**
   - Erst das Alt-Tor, dann Nachmessung der Top 3 mit frischen Seeds.
   - Danach läuft die versiegelte Gruppe **einmal**, gepaart mit Phase 8, und es werden nur Summen gemeldet.
   - **Kein Merge**, Leon entscheidet.

## Verlauf

### Runde A

- 05.10. 09:48: Start der Runde. Um 10:35 beendete ein Neustart der Sitzung die Trainingsprozesse; der Autopilot
  setzte sie vom letzten Checkpoint fort.
- **+1 Mio.** (Arm 2e-5, EMA, kleine Messung):
  - dev_alt 64,5 % (Startmodell 67,7 %), Prüfung 19/32.
  - **Auffällig ist die Drift.** Nach 0,5–0,8 Mio. Schritten liegt die KL zu Phase 8 bei 0,13–0,15, das ist über
    der Delle aus Phase 9 (0,087). Nur noch 76 % der Entscheidungen stimmen mit Phase 8 überein.
  - Vermutete Ursache ist die geänderte Belohnung: Weg-Belohnung statt Rechts-Belohnung, mit der Phase 8 trainiert
    wurde. Die Lernrate allein erklärt die Drift nicht.

- **Tempo:**
  - Bei der kleinen Lernrate erreicht PPO die KL-Abbruchschwelle (`target_kl`) nie, deshalb laufen in jedem Update
    alle Epochen. Etwa 85 % der Zeit gehen ins Update, die Arme schaffen 190–240 Schritte/s statt 430 in Phase 9.
  - Zusätzlich bremste ein auf Kern 3 gepinnter Auswerter den Arm, der sich diesen Kern teilte: Mit 2 Threads
    wartet jeder Schritt auf den langsamsten. Der Auswerter läuft seitdem mit nice 10 auf allen Kernen.
- **Urteil (05.10. 15:14, nach Regel):**

  | Arm | Alt-Verlust (dev_alt, EMA + roh, +2/+3/+4 Mio.) | Wächter-Val bei +4 Mio. | Drift-KL am Ende |
  |---|---|---|---|
  | 2e-5 | −3,8 Pp | 63 % (EMA) / 59 % (EMA2) | 0,24 |
  | 5e-5 | −3,2 Pp | 57 % / 62 % | 0,22 |

  Startmodell 67,7 %, P8 auf dem Wächter 77 %. → **Keine Lernrate sicher** → Runde B mit **Anker** in beiden Armen,
  Lernraten 3e-5 → 2e-5 → 2e-5.
- **Was wir daraus lernen:**
  - Die Lernrate war nicht der Hebel, die doppelte Rate verlor sogar etwas weniger.
  - Auch mit nur Phase-8-Leveln und kleiner Lernrate entfernt sich das Netz breit vom Phase-8-Verhalten.
  - Am deutlichsten zeigt sich das auf den langen Wächter-Leveln (−15 bis −20 Pp).
  - Hauptverdacht ist der Wechsel von der Rechts-Belohnung (mit ihr lernte Phase 8) auf die Weg-Belohnung mit dem
    neuen Zeitlimit.
  - Ohne den Wächter wäre der Einbruch auf langen Leveln unsichtbar geblieben; dev_alt allein zeigte nur −3 bis −4 Pp.

### Lehrer-Fenster

- 05.10. ab 15:14, auf allen 4 Kernen, ohne Training parallel: 2500 Lehrer-Beispiele, Übungsproben v11,
  Anker-Zustände und der BC2-Cache.

*(Fortsetzung folgt.)*
