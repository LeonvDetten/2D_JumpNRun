# Lerntagebuch 11 – Phase 11: Generalist (beide Richtungen, lange Level, Doppelgabel)

Rohdaten und Regeln: `docs/lernen/daten/phase11_vorregistrierung.json` (alle Schwellen, vor dem ersten
Trainingsschritt committet), `runs/phase11/state.json` (Autopilot-Protokoll), `jumpnrun/rl/autopilot11.py`,
`milestones11.py`, `status11.py`. *Entwurf – wird während der Phase ergänzt.*

## Ausgangslage

Phase 10 endete mit dem Lehrer-Kandidaten (Runde D, EMA2 72M) als bestem Modell.
- **Besser als P8:** dev_alt 67,5 % gegenüber 66 %, Prüfung 51/64 gegenüber 46/64.
- **Nicht besser:** Wächter-plus und die Summe auf dem handmade8-Test.
- **Gar nicht gelöst:** gespiegelte lange Level (Truhe links) mit 0 %.

Leons Ziel ist ein **Generalist**, der alle Level in beide Richtungen schafft, egal wie komplex. Deshalb gibt es
keine Rechts-Belohnung auf Phase-8-Leveln.

Leons Entscheidungen vom 7. Oktober:
- zwei Arme, A mit 15 % gespiegelten Leveln und B ohne,
- je 8 Mio. Schritte,
- die Routine „Phase 10 Wächter“ wird durch „Phase 11 Wächter“ ersetzt.

## Schritt 0 – Diagnose doppelgabel

Je 16 Episoden auf dem erlaubten Dev-Level doppelgabel (`scripts/diag_doppelgabel11.py`, Daten in
`docs/lernen/daten/phase11_diag_doppelgabel.json`):

| | P8 | Phase-10-Lehrer |
|---|---|---|
| Ende | stuck, alle 16 | stuck, alle 16 |
| Umkehren auf der oberen Straße | 0–1 Mal | 7–10 Mal |
| P(links) während des Steckenbleibens | ≈ 0,26 | ≈ 0,44 |
| Bereich, in dem sie stecken | Spalte 20–43 | Spalte 20–42 |

- **P8** läuft oben stur gegen die Wand.
- **Der Lehrer** kehrt zwar um, läuft bis an das linke Ende der Straße (Spalte ≈ 20) und kehrt dort wieder um.

Der Grund liegt in der Geometrie: Zwischen der obersten Treppenstufe und der Straße ist eine 2 Felder breite
Lücke, unter der Boden liegt. Der Bot behandelt sie wie eine tödliche Grube.

**Lehre aus einem Fehlstart:**
- Die erste Fassung der Übungsart `lange_sackgasse` nutzte die Gabel des Generators. Dort setzt die Straße
  direkt an der Treppe an.
- Der Lehrer schaffte diese Proben zu **100 %**, doppelgabel aber weiter **0/16**. Das Problem war also nicht getroffen.
- Die zweite Fassung (`_long_fork` in `jumpnrun/levelgen/skills.py`) variiert:
  - die Lücken zwischen den Stufen (1–3 Felder, Boden darunter),
  - die Lücke zwischen Stufe und Straße (0–3 Felder),
  - die Höhe der Straße.
- Auf diesen Proben schafft der Lehrer 61 % und P8 12,5 %. Die beiden Arme wurden nach 200k Schritten (noch im
  Warm-up) neu gestartet; der Fehlstart liegt in `runs/phase11/fehlstart`.

## Bausteine

- **Übungsart `lange_sackgasse`** (8. Art, doppelt gewichtet):
  - d0: Start an der Wand einer 20–28 Felder langen Sackgasse,
  - d1: Sackgasse von 30–40 Feldern mit einem Gegner unten,
  - d2: zwei solche Gabeln hintereinander, mit normalem Start.
  - Proben: `levels/probes/v12_lange_sackgasse.json`.
- **Lange Level** (`LongSource`, 10 % der Schritte): zwei Generator-Level der Stufen 8–12 hintereinander,
  ≈ 300–650 Felder lang.
- **Gespiegelte Level** (`MirrorSource`, nur Arm A, 15 %): davon ein Drittel gespiegelte lange Level (Truhe weit links).
- **Lehrer P8** auf eigenen Zuständen: Das Gewicht fällt linear von 1,0 auf 0,3 bis +4,15 Mio. und bleibt dann
  konstant bei 0,3.
- **BC2** wie Runde D. Arm A bekommt zusätzlich die 353 gespiegelten Lehrer-Demos.
- **Übernommene Fehlerbehebungen aus dem Neustart-Zweig:**
  - *Gegnerrichtung der gespiegelten Phase-9-Demos:* Beim Abspielen liefen die Gegner falsch herum,
    17 statt 51 von 51 gewannen. Das betraf auch die BC2-Daten von Phase 10.
  - *Atomarer Cache:* Ein Neustart findet nie eine halb geschriebene Datei.
  - *channels_last:* etwa 3× schnelleres Netz-Update bei gleichen Ausgaben.
  - *Zentraler Übungsstand:* wird in `curriculum.json` gesichert.
  - *Stufen-Curriculum:* nur aus Phase-8-Episoden.
  - *Checkpoint- und EMA-Neustartfehler* behoben.
- **Hinweis:** Das Startmodell bringt aus Runde C/D einen schwachen Anker zu P8 mit (Gewicht 0,01). Er bleibt
  unverändert, damit Phase 11 direkt an Runde D anschließt.

## Basiswerte (milestones11, Seed 0)

| | Phase-10-Lehrer | P8 |
|---|---|---|
| dev_alt | 67,5 % | 64,5 % |
| Prüfung | 51/64 | 44/64 |
| F | 43,4 % | 7,5 % |
| doppelgabel | 0/16 | 0/16 |
| Gespiegelt (alt / lang) | 0 % / 0 % | 0 % / 0 % |
| Wächter-plus (12 × 32) | 77,3 % | 78,1 % |
| Sackgasse-Proben v12 | 61,3 % | 12,5 % |
| **G** | **37,8 %** | **23,0 %** |

## Verlauf

*(wird während des Trainings ergänzt)*
