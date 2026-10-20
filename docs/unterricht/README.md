# Unterricht: STATION Q

[← zurück zur Dokumentation](../README.md)

**[station-q.html](station-q.html)** ist eine Lern-App über Reinforcement Learning für die Klassen 12/13. Sie
reicht für etwa 8 Wochen à 2–3 Stunden und besteht aus einer einzigen Datei (≈ 5 MB). Sie läuft komplett offline:
kein Server, kein Konto, nichts wird nachgeladen. Niemand schreibt Code. Die Schülerinnen und Schüler arbeiten mit
Reglern, Experimenten, Vorhersagen und Quiz.

## Inhalt

- **16 Missionen in 5 Akten:** vom „Sei der Agent“ über Banditen, Wertiteration, Q-Learning, Belohnungsdesign,
  neuronale Netze, DQN, Neuroevolution, Imitation, PPO und ehrliches Messen bis zu RLHF und einer Abschluss-Liga.
- **Ablauf jeder Mission:**
  1. Echte Beobachtung aus diesem Projekt.
  2. Die Vorhersage wird versiegelt.
  3. Experiment.
  4. Auflösung.
  5. Quiz.
  6. Merke.
  7. Logbuch-Karte mit einer echten Zahl aus dem [Lerntagebuch](../lernen/00_ueberblick.md).
- **Der echte Bot** (float16-Gewichte, ≈ 1 Mio. Parameter) spielt live im Browser das Prüfungslevel von 2023:
  - mit Röntgenblick, Temperatur- und Störungsregler;
  - in „Knack den Bot“ bauen die Schüler Level, die der Löser als lösbar beweist, und suchen damit Schwächen des Bots.
- **Seiten:** Sternkarte (Fortschritt), Laborbuch (Export als HTML oder JSON), Glossar mit 95 Begriffen und der
  Lehrkraft-Bereich (PIN `2026`). Im Lehrkraft-Bereich stehen:
  - Wochenpläne für 16, 20 oder 24 Stunden;
  - Lösungen und Stolperfallen je Mission;
  - Faktenblatt, Klassenübersicht und Beamer-Werkzeuge.

## Öffnen und verteilen

1. Die Datei dort hochladen, wo die Klasse sie **per Link in Safari** öffnet: Moodle, IServ oder Schul-Webspace.
   Bei Moodle die Anzeige auf „Öffnen“ stellen.
2. **Nicht** über die Dateien-App öffnen. Ihre Vorschau führt kein JavaScript aus, man sieht dann nur eine
   Hinweiskarte. Voraussetzung ist iPadOS ab 16.4.
3. Der Lernstand liegt im Browser des jeweiligen Geräts. Darum am Stundenende über Zahnrad → Exportieren sichern.
   Die Lehrkraft lädt die Exportdateien für die Klassenübersicht.

## Geprüft und offen

- **Geprüft** in Chromium mit Touch-Simulation:
  - alle Tabs bei 1024×768, 768×1024, 1180×820 und 1366×1024, hell und dunkel;
  - Offline-Start, Export und Import;
  - 326 Unit-Tests: Physik bitgleich zu Python, Bot-Parität, jede Behauptung der Experimente;
  - Faktencheck aller Projektzahlen gegen das Lerntagebuch.
- **Nicht geprüft:**
  - ein echtes iPad mit Safari;
  - die Videowiedergabe in Mission 13 (dem Test-Browser fehlt H.264);
  - wie lange das Live-Training auf älteren iPads dauert.

  Vor dem Einsatz einmal auf einem Klassen-iPad durchklicken.
- **Quellen:** Das Quellprojekt (Module, Engines, Tests, Build) liegt nicht im Repo. Die HTML-Datei ist der
  vollständige Stand.
