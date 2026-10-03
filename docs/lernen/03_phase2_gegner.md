# Lerntagebuch 3 – Phase 2: Gegner und Plattformen

Interaktive Version: `docs/lernen/seiten/phase2.html` (mit Video `zeitraffer_phase2.mp4` im selben Ordner).

## Aufbau

- Start mit dem fertigen Phase-1-Netz (**Transfer Learning** / Feintuning), Stufen 0–5.
- Training auf 12.070 verschiedenen generierten Leveln plus 6 handgebauten (`levels/phase1/`, `levels/phase2/`).
- 2,1 Mio. Schritte (1,5 → 3,6 Mio. gesamt), zweimal durch Container-Neustarts unterbrochen und vom
  letzten Checkpoint fortgesetzt. Modell: `models/phase2.zip`.

## Ergebnisse (Test-Level, nie trainiert, je 20 pro Stufe)

| Stufe | Bot nach Phase 1 | Bot nach Phase 2 |
|---|---|---|
| 0–2 | 19–20 | 20 |
| 3 Gegner | 12 | 20 |
| 4 Plattformen | 8 | 20 |
| 5 alles | 5 | 19 |
| 6 dicht (nie trainiert) | 4 | 19 |
| 7 Experte (nie trainiert) | 0 | 16 |

Zeitraffer auf `levels/showcase/gegner.txt`: 7/32 → 6/32 → 30/32 → 31/32 im Ziel.

## Was der Bot mit Gegnern macht

Von 174 Gegnern, an denen der Phase-2-Bot vorbeikam: **135 übersprungen, 39 plattgesprungen, 0 abgeschossen.**
Die Aktion „schießen“ wählt er in 0,4 % der Schritte.

**Warum?** In Phase 1 war Schießen nutzlos, also hat das Netz es fast abgeschaltet. In Phase 2 funktioniert
Drüberspringen gut genug – der Bot hat keinen Anlass, Schießen wiederzuentdecken. Das ist ein
**lokales Optimum**: Ein Bot lernt nur, was er ausprobiert. Der Entropie-Bonus (0,01) ist zu schwach,
um eine einmal verworfene Fähigkeit zurückzuholen. Zum Problem wird das erst, wenn ein Level Schießen
erzwingt (z. B. ein Gegner in einem niedrigen Gang).

## Curriculum-Formel

Gewicht einer Stufe = `s · (1 − s) + 0,05` (s = aktuelle Erfolgsrate). Maximal bei 50 %, so übt der Bot
bevorzugt an der Grenze seines Könnens. Neue Stufe bei ≥ 60 % auf der bisher schwersten.
Weil der Bot sein Können aus Phase 1 mitbrachte, waren die Stufen 3–5 nach 23.000–56.000 Schritten frei.

## Kein Vergessen

Stufen 0–2 blieben bei 20/20 – das Curriculum mischt leichte Stufen immer wieder unter und verhindert so
*catastrophic forgetting*.

## Prüfungslevel

- `levels/exam/level.txt` – Original von 2023 (plus ein Block für die neue Physik): **Bonus-Prüfung**
- `levels/exam/level_entschaerft.txt` – nur 4 statt 12 Gegner fallen am Start auf die Treppe: **offizielle Prüfung**.
  Mit dem Löser (Wegpunkte, Gegner simuliert) nachweislich schaffbar; die gefundene Lösung liegt in
  `level_entschaerft.loesung.json` und wird von einem Test nachgespielt.
