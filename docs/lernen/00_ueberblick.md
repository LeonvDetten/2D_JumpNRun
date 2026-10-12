# Lerntagebuch 0 – Überblick: Was ist Reinforcement Learning?

> **Stand 12.10.2026:**
> - Der aktuelle Bot ist `models/space_pirate_bot.zip` (Phase 13). Er schafft das Prüfungslevel von 2023 in 98 %
>   der Versuche, mehr in [docs/bot.md](../bot.md).
> - Interaktiv zum Ausführen: [`projekt_interaktiv.ipynb`](projekt_interaktiv.ipynb), Lesefassung als
>   [HTML](projekt_interaktiv.html). Es führt mit echtem Projektcode und dem trainierten Bot durch alle Phasen und
>   Ansätze (Stand 11.10.; alle 24 Code-Zellen laufen mit dem aktuellen Code durch, geprüft am 12.10.).
> - Zurück zur [README](../../README.md).

## Die Grundidee in einem Satz

Ein **Agent** (unser Bot) probiert in einer **Umgebung** (dem Spiel) **Aktionen** aus, bekommt dafür
**Belohnungen** und lernt daraus eine **Strategie** (*Policy*), die auf Dauer möglichst viel Belohnung einbringt.

Niemand sagt dem Bot, *wie* man über eine Lücke springt. Er erfährt nur: „Weiter rechts = gut, Grube = schlecht,
Truhe = sehr gut“. Den Rest findet er durch Ausprobieren heraus.

## Die Begriffe am Beispiel unseres Spiels

| Begriff | Bedeutung | Bei uns |
|---|---|---|
| **Umgebung** (*Environment*) | die Welt, in der der Agent handelt | das Jump'n'Run (`jumpnrun/rl/env.py`) |
| **Beobachtung** (*Observation*) | was der Agent von der Welt sieht | 13 × 25 Kacheln um den Spieler + ein paar Zahlen (Geschwindigkeit, am Boden?, …) |
| **Aktion** | was der Agent tun kann | 6 Stück: nichts, links, rechts, springen, rechts+springen, schießen |
| **Schritt** (*Step*) | eine Entscheidung | eine Aktion, die 4 Frames lang gehalten wird (≈ 0,13 s) |
| **Belohnung** (*Reward*) | Zahl nach jedem Schritt | +0,1 pro neuer Kachel nach rechts, −1 bei Tod, +2 an der Truhe |
| **Episode** | ein Versuch von Start bis Ende | ein Level, bis Truhe / Tod / Zeit abgelaufen |
| **Policy** | die Strategie: Beobachtung → Aktion | ein neuronales Netz (`jumpnrun/rl/policy.py`) |
| **Value** | Schätzung „wie viel Belohnung kommt ab hier noch?“ | zweiter Ausgang desselben Netzes |

## Wie lernt der Bot? (PPO in einfachen Worten)

1. **Spielen:** 8 Spiele laufen parallel, der Bot sammelt ~2.000 Schritte Erfahrung
   (Beobachtung, gewählte Aktion, Belohnung).
2. **Bewerten:** Für jeden Schritt wird geschätzt, ob die Aktion *besser oder schlechter als erwartet* war
   (der *Vorteil*, engl. *Advantage*). Dafür braucht man den Value-Ausgang.
3. **Verbessern:** Das Netz wird so angepasst, dass Aktionen mit positivem Vorteil wahrscheinlicher werden –
   aber **nur ein kleines Stück** (das „Proximal“ in PPO), damit eine unglückliche Runde nicht alles Gelernte zerstört.
4. Wiederholen – ein paar tausend Mal.

## PPO oder DQN?

| | **DQN** (Deep Q-Network) | **PPO** (Proximal Policy Optimization) |
|---|---|---|
| lernt | eine Punktzahl pro Aktion („Q-Wert“), wählt die beste | direkt Wahrscheinlichkeiten für Aktionen |
| Daten | speichert alte Erfahrungen und lernt immer wieder daraus (dateneffizient) | nutzt jede Erfahrung nur kurz, braucht mehr Spielzeit |
| Stabilität | empfindlich bei Einstellungen | gilt als robust, „funktioniert meistens“ |
| parallel spielen | möglich, aber weniger natürlich | ideal: viele Spiele gleichzeitig |

**Warum PPO bei uns:** Unser Spiel ist sehr schnell simulierbar (~19.000 Frames/s pro CPU-Kern), Spielzeit ist also
billig – der Nachteil von PPO fällt kaum ins Gewicht, die Robustheit dafür sehr.

## Warum hat der alte Ansatz nicht funktioniert?

Beim Neustart haben wir im Spielcode Probleme gefunden, die RL-Training fast unmöglich machen
(Details im nächsten Kapitel):

- **Man konnte in Gruben nicht sterben** – der Spieler fiel einfach ewig. Der Bot bekam nie das Signal „Grube = schlecht“.
- **Die Spielzeit hing an der echten Uhr** (`pygame.time.get_ticks()`). In schneller Simulation stimmen dann
  Schuss-Abklingzeit und andere Regeln nicht mehr; zwei gleiche Spiele verlaufen unterschiedlich.
- **Sprünge waren niedriger als ein Block** – Stufen gingen nur über einen Kollisions-Trick, den ein Bot
  entweder nie findet oder gnadenlos ausnutzt.
- Dazu eine **sehr komplizierte Belohnung** mit vielen Zusatzregeln. Je mehr Regeln, desto eher lernt der Bot,
  die Regeln auszutricksen statt das Spiel zu spielen.

Unser Grundsatz diesmal: **erst ein sauberes, deterministisches Spiel, dann eine minimale Belohnung,
und jeder Schritt wird sichtbar überprüft.**

## Aufbau des Projekts

Die heutige Struktur mit App, Editor und UI steht in der [Architektur](../architektur.md). Für das Lernen
wichtig sind:

```
jumpnrun/core/          das Spiel als reine Simulation (keine Grafik, keine Uhr)
jumpnrun/levelgen/      Level-Generator + Löser (prüft, ob ein Level schaffbar ist)
jumpnrun/rl/            Umgebung, Netz, Curriculum, Training, Auswertung, Geister-Ansicht
jumpnrun/imitation/     Musterlösungen vom Löser, Behavior Cloning, DAgger
levels/                 exam/ (Prüfung), test_serie/, phase1/ … (Trainingslevel), showcase/ (für Videos)
models/                 die Lernstände aller Phasen
docs/lernen/            dieses Lerntagebuch, daten/ (Rohdaten), medien/ (Bilder), seiten/ (Lernseiten, Videos)
```

## Die Phasen

| Phase | Ziel | Kapitel |
|---|---|---|
| 0 | sauberer Spielkern, Physik, Tests, Löser | [01_phase0_spielkern.md](01_phase0_spielkern.md) |
| 1 | erster Bot: laufen und über Lücken springen | [02_phase1_erster_bot.md](02_phase1_erster_bot.md) |
| 2 | Gegner, Plattformen, Curriculum | [03_phase2_gegner.md](03_phase2_gegner.md) |
| 3 | Generalist auf zufälligen Leveln, erste Prüfung | [04_phase3_pruefung.md](04_phase3_pruefung.md) |
| 5 | Vom Löser abschauen, feinere Steuerung | [05_phase5_abschauen.md](05_phase5_abschauen.md) |
| 6 | Übersichtskarte, lange Level, Startpunkte – **erste Prüfungssiege** | [06_phase6_generalist.md](06_phase6_generalist.md) |
| 7 | Zwei Netze im Vergleich, EMA, Abzweige – Prüfung 85/128 (Ziel erreicht), Test-Serie 138/192 (Ziel 144 verfehlt), geheime exam2 49/128 – **Ziel insgesamt verfehlt** | [07_phase7_zwei_wege.md](07_phase7_zwei_wege.md) |
| 8 | Ehrlich messen: vier Messgruppen, Fähigkeits-Proben, 12 neue Level, Datenweg + Augmentierung, Runden gegen Kontrolle – versiegelt 208/256 (untere 95-%-Grenze 76 %), exam2 85/128, Test-Serie 153/192 – **Merge-Kriterium erfüllt**; Gabelungen bleiben offen | [08_phase8_ehrlich_messen.md](08_phase8_ehrlich_messen.md) |
| 9 | Umkehren und Kanäle: Weg-Distanz-Belohnung, 7. Aktion „links+springen“, Sicht nach hinten, Generator v10 (Kanäle, Mario-Bausteine), Augmentierung v2, Lehrer-Beispiele – neue versiegelte Level 32/128 (= Phase 8), Phase-8-versiegelt 156/256 – **Merge-Kriterium nicht erfüllt**; Erkenntnis: ohne Vorbild probiert der Bot „links“ nie | [09_phase9_umkehren.md](09_phase9_umkehren.md) |
| 10 | Halten, üben, mischen: Messreparatur, kurze Übungslevel, zweiter Vorbild-Strom, Mischung nach Schritten. Neue Fähigkeiten werden lernbar (Kanal-Probe ≈ 90 %), dafür geht auf langen alten Leveln etwas verloren | [10_phase10_halten_ueben_mischen.md](10_phase10_halten_ueben_mischen.md) |
| 10b | Neustart-Arm: ein frisches Netz mit Kickstarting von P8. Es holt das P8-Niveau in ~30 Mio. Schritten zurück und lernt Alt und Neu gemeinsam; das Alt-Tor (Wächter) bleibt verfehlt | [10b_neustart.md](10b_neustart.md) |
| 11 | Generalist in beide Richtungen: gezielte Übung löst die Doppelgabel in ~2 Mio. Schritten (0 → 66–81 %); Prüfung 66 % in Arm A | [11_phase11_generalist.md](11_phase11_generalist.md) |
| 12 | Frischer Schüler mit mehreren Lehrern, schwererer Generator, Temperatur 0,3. Auf den versiegelten, nie gesehenen Leveln **75 % gegenüber 62,5 % bei P8** | [12_phase12_generalist_schueler.md](12_phase12_generalist_schueler.md) |
| 13 | Links-Präzision und Nachschärfen: Generalist 87,0 %, Gabeln 90 %, **Prüfung 98 %**, wird zum aktuellen Bot `space_pirate_bot.zip`; offen bleiben Links und Spiegel (52 %) | [13_phase13_links.md](13_phase13_links.md) |

Weitere Texte: die [Reflexion nach Phase 7](../reflexion/phase7_reflexion.md) und ihre
[Gegenprüfung](../reflexion/phase7_gegenpruefung.md). Lernseiten mit Videos liegen in [`seiten/`](seiten/).
