# Lerntagebuch 4 – Phase 3 und Prüfung

Interaktive Version: `docs/lernen/seiten/phase3.html` (Videos `pruefung_geister.mp4` und `pruefung_loeser.mp4` im selben Ordner).

## Phase 3: der Generalist

- Training auf allen Stufen 0–9, Start mit `models/phase2.zip`, 3,6 → 11,05 Mio. Schritte. Modell: `models/phase3.zip`.
- Neue Stufen 8–9 mit Kletterpassagen, Gegnergruppen, herabfallenden Gegnern.
- Während des Trainings wurde der Bot regelmäßig auf dem Prüfungslevel **beobachtet (nicht trainiert)**.
  Dreimal hat das eine Lücke im Training gezeigt, dreimal wurde der Generator erweitert:

| Schritte | Beobachtung | Änderung |
|---|---|---|
| 4,65 Mio. | alle laufen unten, Grube bei Kachel 100 | lange Sackgassen (Boden endet 20–35 Kacheln später) |
| 7,15 Mio. | 10/16 nehmen den oberen Weg, stürzen an Einzelblöcken ab | Trittsteine mit 3 Kacheln Abstand |
| 8,45 Mio. | Sprung 99 → 103 geht zusätzlich eine Reihe hoch, Löser bremst in der Luft | Trittsteine mit Höhenwechsel |

Validierung (je 20 generierte Level der Stufen 4–9, nie trainiert): **99 / 120**.

## Prüfung (32 Versuche je Version, mit Zufall)

| Version | geschafft | häufigstes Ende |
|---|---|---|
| entschärft (4 Startgegner) | 0 / 32 | Grube bei Kachel 90–103 (25×) |
| original (12 Startgegner) | 0 / 32 | Gegnerregen am Start (17×), Grube bei Kachel 100 (11×) |

Weitester Versuch während des Trainings: 48 % (bei 7,75 Mio. Schritten).
Beide Versionen sind nachweislich lösbar (`levels/exam/*.loesung.json`, Video `pruefung_loeser.mp4`).

## Warum

1. **Die Falle liegt außer Sicht:** Der Bot sieht 19 Kacheln voraus, der Boden endet ~60 Kacheln nach der Weggabelung.
2. **Präzision:** 3er-Lücke mit Höhenwechsel auf Einzelblöcke braucht Bremsen in der Luft; der Bot entscheidet nur alle 4 Frames.
3. **Lokales Optimum:** Dauerhüpfen funktioniert fast überall, daher wenig Druck, Bremsen zu lernen.
4. **Gegnerregen** am Start des Originals.

## Validierung vs. Test

Das Modell wurde auf den Validierungs-Leveln ausgewählt, nicht auf der Prüfung – sonst wäre das Prüfungsergebnis geschönt.

## Mögliche nächste Schritte

A Imitation Learning vom Löser · B Entscheidungen alle 2 Frames · C größeres Sichtfeld · D länger trainieren ·
E auf der Prüfung trainieren (= Auswendiglernen, nur als Gegenbeispiel). Empfehlung: A + B.
