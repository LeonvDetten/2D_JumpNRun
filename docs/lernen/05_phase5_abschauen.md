# Lerntagebuch 5 – Phase 5: Vom Meister abschauen

Interaktive Version: `docs/lernen/seiten/phase5.html` (Video `vergleich.mp4` im selben Ordner).

## Was geändert wurde

| | vorher (Phase 3) | Phase 5 |
|---|---|---|
| Entscheidungen | alle 4 Frames (32 px) | **alle 2 Frames (16 px)** |
| Level | Generator v1 | **Generator v2**: Stil pro Level, Tunnel mit Gegner, Fallschacht, niedrige Decken, zwei Wege, längere Sackgassen; schwere Level vom Löser geprüft |
| Lernen | nur PPO (Ausprobieren) | **Abschauen beim Löser** → DAgger → PPO mit abklingender Vorbild-Bremse |
| PPO | lr 3e-4, clip 0,2, ent 0,01, γ 0,99 | lr 1e-4, clip 0,1, ent 0,003, γ 0,995, target_kl 0,02 |

## Ablauf

1. **Musterlösungen** (`python -m jumpnrun.imitation.demos`): Der Löser spielt 1.104 Level (Stufen 0–9) mit
   gelegentlichen Zufallsschubsern und plant danach neu → 465.000 Vorbild-Schritte. Gespeichert werden nur
   Aktionslisten; Beobachtungen werden deterministisch nachgespielt.
2. **Mehrdeutige Labels:** In 69 % der Schritte gibt es eine gleichwertige zweite Aktion (meist „rechts“ =
   „rechts+springen“ in der Luft). Ziel ist darum die *Menge* gleichwertiger Aktionen:
   `Verlust = −log Σ p(a)`.
3. **Behavior Cloning** (`python -m jumpnrun.imitation.bc`), gestartet mit den Gewichten aus Phase 3:
   98 % Übereinstimmung, aber nur 64/120 Validierungslevel → **Verteilungsverschiebung**.
4. **DAgger:** 400 Level selbst gespielt, 217 Fehlschläge, 211 Rettungen vom Löser (8.417 Schritte).
5. **Value-Warmup** auf den eigenen Returns des Bots (nicht auf denen des Lösers – die wären zu optimistisch).
6. **PPO mit Vorbild-Bremse** (`jumpnrun/rl/ppo_demos.py`): nach jedem Update zusätzliche Nachahmungsschritte,
   Gewicht 0,5 · 0,99^Update. 6 Mio. Schritte (`scripts/train_phase5.sh main`).
7. **Vergleich:** dasselbe ohne Vorbild, gestartet beim Phase-3-Bot (`scripts/train_phase5.sh control`).

## Ergebnisse (20 Validierungslevel je Stufe 4–9, nie trainiert)

Siehe Tabelle auf der Lernseite; Kurzfassung: Phase 3 52/120 → nur Abschauen 64/120 → **Abschauen + PPO 114/120**.

Verhalten auf 60 Test-Leveln (Stufen 5–9): Phase 3 schießt 0 Gegner ab und schafft 3/36 Tunnel-Level,
Phase 5 schießt 28 ab und schafft 34/36. Das Vorbild hat das lokale Optimum „Schießen lohnt nicht“ gebrochen.

Prüfung: weiterhin 0/32 in beiden Versionen. Einige Versuche nehmen jetzt den oberen Weg bis Kachel 74;
die meisten scheitern am Gegnerregen am Start oder an den Einzelblöcken ab Kachel 99.

## Lektionen

- Vorbilder brechen lokale Optima (Schießen, Bremsen in der Luft).
- Nachmachen allein reicht nicht (Fehler schaukeln sich auf) – erst eigenes Üben macht es robust.
- Vielfalt ist wichtiger als Menge: Auf den vielfältigeren Leveln fiel der Phase-3-Bot auf 52/120.
- Validierung ≠ Test: Das Modell mit der besten Validierung ist nicht automatisch das beste auf einem
  ungewöhnlichen Einzellevel.
