# Lerntagebuch 2 – Phase 1: Der erste Bot lernt springen

## Ziel

Der Bot soll lernen, nach rechts zu laufen, über Lücken zu springen und Stufen hochzukommen
(Schwierigkeitsstufen 0–2, noch keine Gegner). Man soll **sehen**, wie er es lernt.

## Was sieht der Bot? (Beobachtung)

Der Bot bekommt kein Bild, sondern eine **Kachel-Karte** – ungefähr das, was du auf dem Bildschirm siehst:

```
13 Zeilen × 25 Spalten (5 hinter dem Spieler, 19 vor ihm), 4 "Ebenen":
  Ebene 0: Blöcke     (1 = Block, auch der Levelrand)
  Ebene 1: Truhe
  Ebene 2: Gegner     (+1 läuft nach rechts, −1 nach links)
  Ebene 3: Spieler    (in welcher Zeile er gerade ist)
```

Dazu 15 Zahlen: Fallgeschwindigkeit, steht er am Boden, Blickrichtung, Schuss bereit?, genaue Position
innerhalb der Kachel, Höhe, und Abstand zu den 3 nächsten Gegnern.

**Warum so?** Eine Grube ist auf der Karte einfach „unten keine 1“. Das Netz kann lernen: „Wenn zwei Spalten
vor mir unten nichts ist, springen!“ – und zwar **egal in welchem Level**, weil es nur auf das Muster schaut.

## Das Netz

```
Kachel-Karte → 3 Faltungsschichten (CNN) ─┐
                                           ├→ 256 Merkmale ─→ Policy: 6 Wahrscheinlichkeiten (Aktionen)
15 Zahlen   → kleine Schicht (64)       ──┘                └→ Value: "wie gut ist die Lage?"
```

Ein **CNN** (Convolutional Neural Network) schiebt kleine 3×3-Filter über die Karte. Jeder Filter erkennt ein
Mini-Muster (Kante, Loch, Stufe) – überall auf der Karte. Das macht den Bot robust gegenüber neuen Leveln.

## Die Belohnung – bewusst minimal

| Ereignis | Belohnung |
|---|---|
| jede neue Kachel weiter rechts als je zuvor | +0,1 |
| Tod (Grube oder Gegner) | −1 |
| Truhe erreicht | +2 |
| Zeit abgelaufen (150 Schritte ohne Fortschritt) | Episode endet ohne Strafe |

Keine Extra-Regeln wie „Sprung-Bonus“ oder „Abstand zur Truhe“. Jede Zusatzregel ist eine Einladung zum
Schummeln: Gäbe es einen Sprung-Bonus, würde der Bot lernen, auf der Stelle zu hüpfen.

## Curriculum – vom Leichten zum Schweren

Am Anfang gibt es nur Stufe 0 (einfach zur Truhe laufen). Sobald der Bot eine Stufe zu 60 % schafft, wird die
nächste freigeschaltet. Danach werden Stufen bevorzugt, die er **etwa zur Hälfte** schafft – dort lernt er am
meisten. Leichte Stufen kommen trotzdem ab und zu dran, damit er nichts verlernt.

Zusätzlich kommen in 20 % der Episoden die handgebauten Level aus `levels/phase1/` dran.

## PPO-Einstellungen (und was sie bedeuten)

| Einstellung | Wert | Bedeutung |
|---|---|---|
| parallele Spiele | 8 | mehr Vielfalt pro Lernrunde |
| `n_steps` | 256 | Schritte pro Spiel und Runde → 8 × 256 = 2.048 Erfahrungen pro Runde |
| `batch_size`, `n_epochs` | 512, 4 | jede Runde wird in 4 Durchgängen zu je 4 Päckchen gelernt |
| `learning_rate` | 3·10⁻⁴ → 3·10⁻⁵ | Schrittgröße beim Lernen, wird zum Ende kleiner |
| `gamma` | 0,99 | wie weit der Bot in die Zukunft denkt (≈ 100 Schritte ≈ 13 s) |
| `ent_coef` | 0,01 | kleiner Anreiz, weiter Neues auszuprobieren |
| `clip_range` | 0,2 | wie stark sich die Strategie pro Runde höchstens ändern darf |

## Ergebnisse

*(wird nach dem Training ergänzt)*
