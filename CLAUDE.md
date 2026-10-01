# Arbeitsweise in diesem Projekt

Leon ist Beobachter und Entscheider bei der Architektur, er schreibt keinen Code. Doku und Chat auf Deutsch,
Code und Kommentare auf Englisch. Große Schritte erst im Planmodus planen und Auswahlmöglichkeiten geben.
Gearbeitet wird auf dem Branch `claude/jumpnrun-cloud-session-65e3po`; nach `main` erst, wenn der Bot das
Prüfungslevel (`levels/exam/level.txt`, wird nie trainiert) sicher schafft.

## Lange Trainingsläufe

- Training per idempotentem Skript starten (`scripts/train_phaseN.sh`, mit `--target` und `--time-limit-hours`),
  gepinnt auf Kerne 0–2; Auswertungen laufen auf Kern 3 (`OMP_NUM_THREADS=1 taskset -c 3`).
- Der Container wird abgeräumt, sobald die Sitzung untätig ist – auch wenn sie nur auf eine offene
  Freigabe-Anfrage wartet (dann sterben die Trainingsprozesse). Darum:
  - durchgehend in Beobachtungsrunden arbeiten (je ~9,5 min Bash, z. B. `bash scripts/phase7.sh`);
  - in den Runden keine Werkzeuge, die nachfragen können (`send_later`, `create_trigger`,
    `list_triggers`, `delete_trigger` …);
  - als Sicherheitsnetz eine stündliche Wächter-Routine pro Phase, einmal zu Beginn angelegt.
- Kommt der Planmodus nur durch einen Neustart zurück und ist der Plan schon freigegeben: Plan nicht neu
  aufrollen, einmal ExitPlanMode mit dem Vermerk „unverändert, nur Neustart“, dann weiter.

- Meilenstein-Auswertung: `python -m jumpnrun.rl.milestones --run runs/<lauf>` (Validierung, Test-Serie,
  Prüfung inkl. „wo enden die Versuche“).

## Zwischenstände für Leon (etwa alle 30 Minuten)

1. `python -m jumpnrun.rl.status --run runs/<lauf>` erzeugt `runs/<lauf>/status.png` und eine Einschätzung.
2. Das Bild per `SendUserFile` in den Chat schicken, dazu 3–5 Sätze:
   - was seit dem letzten Update passiert ist (Schritte, neue Meilensteine, Bestwerte),
   - wo der Bot auf dem Prüfungslevel scheitert (Engpass-Abschnitt),
   - **kritische Einschätzung**: Lohnt sich Weiterlaufen? Oder dreht es sich im Kreis und es braucht einen
     Eingriff (Trainingsdaten/Generator, Netzgröße oder -art, Belohnung, Hyperparameter)? Konkreten Vorschlag
     nennen, damit Leon entscheiden kann, ob er unterbricht.
3. Bei „Plateau“ oder „Rückschritt“ ausdrücklich fragen, ob abgebrochen und umgeplant werden soll –
   aber ohne Antwort das Training nicht stoppen (Zeitlimit gilt).
