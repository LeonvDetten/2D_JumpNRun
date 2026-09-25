# Lerntagebuch 0 – Überblick: Was ist Reinforcement Learning?

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

```
game.py                 selbst spielen (Tastatur)
jumpnrun/core/          das Spiel als reine Simulation (keine Grafik, keine Uhr)
jumpnrun/render/        Grafik: Spiel, Geister-Ansicht, Videos
jumpnrun/levelgen/      Level-Generator + Löser (prüft, ob ein Level schaffbar ist)
jumpnrun/rl/            Umgebung, Netz, Curriculum, Training, Auswertung, Geister-Ansicht
levels/                 exam/ (Prüfung), phase1/ phase2/ … (Trainingslevel), showcase/ (für Videos)
tests/                  automatische Tests
docs/lernen/            dieses Lerntagebuch
```

## Die Phasen

| Phase | Ziel | Kapitel |
|---|---|---|
| 0 | sauberer Spielkern, Physik, Tests, Löser | [01_phase0_spielkern.md](01_phase0_spielkern.md) |
| 1 | erster Bot: laufen und über Lücken springen | [02_phase1_erster_bot.md](02_phase1_erster_bot.md) |
| 2 | Gegner, Plattformen, Curriculum | folgt |
| 3 | Generalist auf zufälligen Leveln | folgt |
| 4 | Abschlussprüfung auf deinem Original-Level | folgt |
