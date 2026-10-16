# Mission Schatzkiste – Reinforcement Learning für den Unterricht

[← zurück zur Doku-Übersicht](../README.md)

[`mission_schatzkiste.html`](mission_schatzkiste.html) ist eine einzelne HTML-Seite für Schülerinnen und Schüler. Sie
zeigt am Beispiel von Space Pirate das große Bild, wie man einem Programm mit Reinforcement Learning (RL) ein
Spiel beibringt: erst selbst „Bot sein“, dann die Begriffe, dann der Bauplan in sechs Schritten. Die Seite ist
selbst wie ein Jump'n'Run aufgebaut, mit fünf Leveln, Checkpoints und einer Schatzkiste.

| | |
|---|---|
| **Datei** | `mission_schatzkiste.html`, etwa 1,1 MB, alles eingebettet (auch das GIF) |
| **Datei holen** | Auf GitHub zeigt ein Klick auf die Datei nur Quelltext. Dort oben rechts „Download raw file“ (Pfeil nach unten) wählen und die gespeicherte Datei per Doppelklick öffnen. Auf Lernplattformen als Datei hochladen, nicht in eine Textseite kopieren. |
| **Technik** | reines HTML: kein CSS, kein JavaScript, keine externen Dateien. Läuft offline, auf Lernplattformen wie Moodle, auf dem Handy und am Beamer (dort mit Strg/Cmd + Plus auf 150–200 % vergrößern, denn die Buchstaben-Gitter sind kleiner als der Text) |
| **Zielgruppe** | ab etwa Klasse 8, kein Vorwissen nötig |
| **Dauer** | 20–25 Minuten allein, als Unterrichtsstunde 45 Minuten |
| **Material** | ein Gerät pro Paar, Zettel und Stift für den Punktezettel |

## Lernziele

Die Schülerinnen und Schüler können
- den RL-Kreislauf (Agent, Umgebung, Beobachtung, Aktion, Belohnung) an einem Spiel beschreiben,
- erklären, dass ein Bot lernt, was belohnt wird – nicht, was gemeint ist –, und Schummelgefahren einer Belohnung
  benennen,
- den Bauplan in sechs Schritten nennen und in einem Steckbrief auf Snake oder Flappy Bird übertragen,
- begründen, warum ein Bot auf nie gesehenen Leveln geprüft werden muss.

## Aufbau der Seite

| Station | Kernaussage | Bauplan-Teil | Checkpoint |
|---|---|---|---|
| Start | RL = Lernen durch Ausprobieren und Belohnung; Spielregeln der Seite | – | – |
| Level 1: Sei der Bot! | Drei echte Spielszenen als Buchstaben-Gitter, Aktionen zum Aufklappen. Danach Agent, Umgebung, Beobachtung, Aktion, Belohnung, Episode, Return, Policy; auch spätere Punkte zählen | – | Tür B |
| Level 2: Die Welt des Bots | Der Bot sieht nur Zahlen. Vor dem Lernen kommt eine faire, deterministische, schnelle Simulation; dann wird festgelegt, was er sieht und tun darf | 1, 2 | Tür C |
| Level 3: Die Belohnung | Belohnungs-Labor mit drei Vorschlägen; die echte Belohnung; „Der Bot lernt, was du belohnst – nicht, was du meinst.“ | 3 | Tür A |
| Level 4: Gehirn und Training | Neuronales Netz mit Policy und Value, PPO als Schleife, Curriculum, Lernkurve des ersten Bots. Hier zweigt der Geheimgang ab | 4, 5 | Tür C |
| Level 5: Die Prüfung | Nur nie gesehene und andersartige Level zeigen echtes Können (Generalisierung); Lernkurve auf dem Prüfungslevel; ehrliche Schwächen | 6 | Tür B |
| Schatzkiste | Bauplan in sechs Schritten, Transfer auf Snake oder Flappy Bird, Wertung, Glossar | – | Bossfrage +2 |
| Geheimgang (optional) | Was der Bot nie ausprobiert, lernt er nie; Abschauen beim Löser (Imitationslernen) | – | Bonus +1 |

Die Punkteregel der Seite (richtige Tür +1, falsche Tür −1, Bossfrage +2) ist absichtlich dieselbe Idee wie die
Belohnung des Bots. In Level 3 wird das aufgedeckt, in der Schatzkiste kommt die Frage dazu, ob man hätte
schummeln können. Höchstens 8 Punkte (der Return aus Level 1 zählt nicht mit); die Ränge heißen Landratte
(bis 3), Crew-Mitglied (4–6) und Käpt'n (7–8).

## Wie die Seite ohne JavaScript interaktiv ist

- **Aufklappen:** Türen, Aktionen und Lösungen sind `<details>`-Elemente. Die Türen eines Checkpoints schließen sich
  gegenseitig (`<details name="…">`, ab Chrome/Edge 120, Firefox 130, Safari 17.2). Ältere Browser lassen mehrere
  offen; das stört nicht.
- **Sprunglinks:** Weltkarte, „Weiter“, „Neuer Versuch ab Zug 1“ und die PPO-Schleife („zurück zu Schritt 1“)
  sind normale Anker. Die Zurück-Taste des Browsers springt zurück.
- **Balken:** `<progress>` zeigt die Etappe, `<meter>` die Messwerte. Die Zahl steht immer auch als Text daneben.
- **Bild:** Das GIF passt sich über `srcset`/`sizes` der Bildschirmbreite an, auch das ist reines HTML.
- **Punkte** zählen die Schülerinnen und Schüler auf Papier. Die Seite speichert nichts.
- **Drucken:** Alles Zugeklappte fehlt im Ausdruck: Zug-Ergebnisse in Level 1, Tür-Begründungen, Lösungen und
  Glossar. Auf Papier liest die Lehrkraft die Ergebnisse aus den Lösungen unten vor.
- In manchen Browsern öffnet die Suche (Strg+F) zugeklappte Lösungen.
- **Barrierefreiheit:** Die Seite lässt sich ganz mit der Tastatur bedienen (Tab, dann Enter) und vergrößern. Die
  Gitter und die Kreislauf-Zeichnung liest ein Screenreader nur als Zeichenfolge vor; das Wichtige steht jeweils in
  der Bildunterschrift darunter. In Partnerarbeit beschreibt die andere Person die Szene.

## Ablaufvorschlag für 45 Minuten

| Zeit | Phase | Was passiert |
|---|---|---|
| 0–5 | Einstieg | Das GIF oben auf der Seite, das Video [`bot_pruefung_2023.mp4`](../medien/bot_pruefung_2023.mp4) oder live die [Web-App](https://leonvdetten.github.io/2D_JumpNRun/) mit „Bot zuschauen“ zeigen. Frage: „Wie hat der Bot das gelernt, wenn es ihm niemand erklärt hat?“ |
| 5–14 | Level 1 zu zweit | Eine Person ist der Bot (Agent) und wählt eine Aktion, die andere ist die Umgebung: Sie klappt die Aktion auf und sagt die Punkte an. Punkte des ersten Versuchs notieren, Return ausrechnen. |
| 14–17 | Plenum | Den Kreislauf Agent → Aktion → Umgebung → Beobachtung + Belohnung an die Tafel. Warum kostet ein Absturz in Zug 2 mehr als 1 Punkt? (Die +2,7 aus Zug 3 gehen mit verloren.) |
| 17–35 | Level 2–5 zu zweit | Checkpoints auf dem Punktezettel; wer schneller ist, nimmt den Geheimgang (Abzweig in Level 4). |
| 35–42 | Schatzkiste | Bossfrage: Steckbrief für Snake oder Flappy Bird. Steckbriefe mit dem Nachbarpaar tauschen: „Wie würdet ihr unsere Belohnung austricksen?“ Das Nachbarpaar vergibt die +2. |
| 42–45 | Abschluss | Wertung. Frage: „Wo hat euch die Seite belohnt wie den Bot – und wo hättet ihr schummeln können?“ |

Wird es knapp: Level 5 gemeinsam am Beamer lesen oder die Bossfrage als Hausaufgabe geben.

Varianten:
- **Selbstlernen** (20–25 Minuten, auch als Hausaufgabe): Seite einfach durchspielen lassen.
- **Ohne Rechner aufwärmen** (5 Minuten): Eine Person sucht mit verbundenen Augen einen Gegenstand im Raum und
  bekommt nur Zahlen zu hören („+1“ näher, „−1“ weiter weg). Danach: Was hat geholfen, was war schwer?

## Lösungen und Erwartungshorizont

**Level 1.** Die Ergebnisse wurden in der echten Spielsimulation nachgespielt (eine Aktion etwa 1 s gehalten, in
Zug 3 bis zur Kiste gut 1,5 s). Die Fortschrittspunkte sind als Kachelabstand im Gitter gezählt.

| Zug | Aktion | Ergebnis |
|---|---|---|
| 1 (Lücke) | rechts + springen | +0,4, über die Lücke |
| | rechts | −1, Grube, Versuch vorbei |
| | springen / nichts | 0 |
| 2 (Gegner) | rechts + springen | +0,3, über den Gegner |
| | schießen | 0, aber der Weg ist frei |
| | rechts / nichts | −1, vom Gegner erwischt |
| 3 (Kiste) | rechts + springen | +2,7 (+0,7 Fortschritt, +2 Kiste) |
| | rechts | −1, Grube |
| | links | −0,1 (weg vom Ziel), beim Zurücklaufen wieder +0,1 |
| | springen | 0 |

Bester Return 3,4; wer in Zug 2 schießt, kommt auf der Seite auf 3,1 (im echten Spiel holt er die 0,3 auf dem
freien Weg nach). Wer in Zug 3 erst nach links läuft, kommt für diesen Zug auf 2,6 (−0,1 + 2,7) oder, mit den 0,1 fürs
Zurücklaufen, wieder auf 2,7. Beides ist in Ordnung; im echten Spiel gleichen sich Umwege genau aus.

**Checkpoints:** 1 B, 2 C, 3 A, 4 C, 5 B. Jede Tür begründet auf der Seite, warum sie richtig oder falsch ist.

**Bossfrage:** Musterlösungen für Snake und Flappy Bird stehen auf der Seite. Andere sinnvolle Antworten zählen
auch, etwa als Beobachtung „Abstände zu Wand und Futter in jede Richtung“ statt des ganzen Rasters. Wichtig ist
der letzte Punkt: Die Schülerinnen und Schüler sollen ihre eigene Belohnung angreifen.

**Bonusfrage:** Beim reinen Nachahmen schaukeln sich kleine Fehler auf. Der Bot gerät in Lagen, die das Vorbild
nie gezeigt hat (Fachbegriff: Verteilungsverschiebung). Erst eigenes Üben macht ihn dort sicher.

## Typische Fehlvorstellungen

| Aussage | Antwort |
|---|---|
| „Der Bot versteht das Spiel.“ | Er sieht nur Zahlen und lernt, welche Zahlenmuster zu welchen Knöpfen und Belohnungen passen. |
| „Das Springen wurde einprogrammiert.“ | Vorgegeben sind die Knöpfe, die Beobachtung und die Belohnung, beim heutigen Bot auch Musterlösungen des Lösers. Eine Regel „wann springen“ steht nirgends im Code; das hat der Bot gelernt. |
| „Mehr Belohnungsregeln = besserer Bot.“ | Jede Zusatzregel ist eine Gelegenheit zum Schummeln (Level 3). |
| „98 % heißt perfekt.“ | Auf Leveln nach links oder gespiegelten Leveln sind es nur 52 %; mit weniger Versuchen schwankt die Zahl um einige Prozentpunkte. |
| „RL ist dasselbe wie ChatGPT.“ | Nein. Sprachmodelle lernen zuerst aus riesigen Textmengen. Danach kommt RL dazu: Belohnt werden Antworten, die Menschen besser finden oder die nachprüfbar richtig sind. Das erste ChatGPT wurde dabei mit PPO trainiert – wie der Bot. |

## Bewusste Vereinfachungen

Für Rückfragen kundiger Schülerinnen und Schüler:

- **Ein „Zug“ in Level 1** fasst etwa eine Sekunde zusammen; der echte Bot entscheidet 15-mal pro Sekunde. Die
  Szenen sind echte Ausschnitte aus `levels/phase1/p1_luecken_01.txt`, `levels/exam/level.txt` (Gegner so, wie sie
  nach dem Start gelandet sind) und `levels/showcase/luecken.txt`. Fortschrittspunkte gibt es im echten Spiel erst
  beim Landen, weil nur auf Stehflächen gemessen wird. In Zug 3 berührt der Pirat die Kiste im Sprung, darum zahlt
  das Training dort +2,4 (+0,4 bis zur Landung, +2 Kiste) statt +2,7.
- **Return ohne Abzinsung:** Die Seite zählt alle Punkte gleich. Genau genommen maximiert PPO den *erwarteten,
  abgezinsten* Return: Eine Belohnung zählt mit jeder Entscheidung, die sie später kommt, nur 0,995-mal so viel.
  Nach 9 Sekunden zählt sie noch halb, nach 30 Sekunden rund ein Zehntel; dasselbe gilt für den Value.
- **Das „Bauchgefühl“** in Level 4 sind ausgedachte Beispielwerte.
- **PPO ohne Formeln:** „besser oder schlechter als erwartet“ ist der *Advantage* (Vorteil). „Nur ein kleines
  Stück“ ist das *Clipping*: Ändert sich die Wahrscheinlichkeit einer Aktion gegenüber dem Stand beim Spielen um
  mehr als 10 % ihres Werts (bei 30 % also über 33 % oder unter 27 %), bringt das im Lernziel keinen weiteren
  Vorteil.
- **Die Lernkurve** in Level 5 zeigt je Lernstand die bessere von zwei Spielweisen. Phase 6 und 7 gewinnen nur mit
  „Temperatur 1“, also so zufällig, wie das Netz trainiert wurde. Ab Phase 8 zählt „Temperatur 0,3“: Die
  Wahrscheinlichkeiten werden geschärft (aus 70 % zu 30 % wird etwa 94 % zu 6 %). Klare Favoriten nimmt der Bot
  fast immer, bei knappen Entscheidungen bleibt ein Rest Zufall, und der hilft gegen Festfahren. Der heutige Bot
  schafft die Prüfung mit Temperatur 1 nur zu 59 %, mit 0,3 zu 98 % (je 256 Versuche,
  `docs/lernen/daten/phase13_urteil.json`). Die Kurve stammt aus `docs/medien/pruefung_messung.json` mit je 64
  Versuchen; für Phase 8 und den heutigen Bot nennt die Seite die genauere Messung mit 256 Versuchen, beide 98 %
  (bei 64 Versuchen 100 % bzw. 94 %, das ist Zufallsschwankung).
- **Die Prüfung ist nicht ganz unberührt:** Trainiert wurde auf dem Original-Level nie. Es hat aber einen
  zusätzlichen Block bekommen, weil es mit sauberer Physik sonst nicht schaffbar war
  ([Lerntagebuch 1](../lernen/01_phase0_spielkern.md)). Außerdem wurde es oft analysiert: Seine Fehlerbilder
  bestimmten, welche Bausteine der Generator baut, und es zählte bei der Auswahl der Modelle mit. Die 98 % können
  darum etwas zu gut ausfallen. Unabhängig messen nur versiegelte Level, die genau einmal am Ende gespielt werden,
  und eine geheime zweite Prüfung ([Lerntagebuch 7](../lernen/07_phase7_zwei_wege.md),
  [8](../lernen/08_phase8_ehrlich_messen.md)). Wie sehr eine Auswahl nach bekannten Leveln täuschen kann, zeigt
  [Lerntagebuch 9](../lernen/09_phase9_umkehren.md).
- **Nicht nur Ausprobieren:** Ganz ohne Vorbild lernten nur die ersten Bots (Phase 1 bis 3). Der heutige Bot
  startete mit Nachahmen von Musterlösungen des Lösers und hatte am Anfang ältere Bots als Lehrer. Auch beim
  anschließenden Üben zieht ihn ein kleiner Nachahm-Anteil weiter zu den Musterlösungen (nie ganz null,
  `jumpnrun/rl/ppo_demos.py`). Die Seite sagt das vereinfacht im Geheimgang.
- **Tempo:** Die 19.000 Spielbilder pro Sekunde gelten für das reine Spiel ohne Netz. Im Training mit Netz sind es
  einige Hundert Entscheidungen pro Sekunde.
- **Rechenzeit:** „Etwa anderthalb Tage“ ist eine Schätzung für die 46 Millionen Schritte des heutigen Bots auf
  3 Prozessorkernen. Das ganze Projekt mit allen Phasen hat ein Vielfaches gebraucht.
- **87 % gegenüber 45 %:** Beide Werte stammen aus der Generalist-Messung über 8 Level-Kategorien, aber aus zwei
  verschiedenen Messrunden (Phase 13 bzw. Phase 12).
- **Ältere Zahlen im Lerntagebuch:** Das Überblickskapitel nennt teils den Stand des ersten Bots (6 Aktionen,
  13 × 25 Kacheln, Belohnung „nach rechts“). Die Seite verwendet die aktuellen Werte aus dem Code.

## Fakten und Quellen

| Angabe auf der Seite | Quelle im Repo |
|---|---|
| 98 % in 256 Versuchen, 87 %, 52 %, 45 % | [`docs/bot.md`](../bot.md), `models/space_pirate_bot.json` |
| Sicht 13 × 33 in 4 Ebenen, Karte bis 120 Kacheln voraus, 23 Messwerte | [`docs/bot.md`](../bot.md); im Code `jumpnrun/rl/env.py`, Konstanten `*_V3` |
| 3.819 Zahlen | 4 · 13 · 33 + 4 · 13 · 40 + 23 |
| 7 Aktionen, 15 Entscheidungen pro Sekunde | `jumpnrun/core/actions.py`, `jumpnrun/core/constants.py` |
| Belohnung ±0,1 / −1 / +2 | `jumpnrun/rl/env.py`, Option `path_delta` (der Kopfkommentar der Datei beschreibt noch den ersten Bot) |
| rund 1 Million Zahlen im Netz (genau 1.040.088) | aus den Gewichten in `models/space_pirate_bot.zip` gezählt |
| 8 Spiele, 4.096 Entscheidungen je Runde, rund 11.000 Runden | Modelldaten in `models/space_pirate_bot.zip` (8 × 512; 46 Mio. ÷ 4.096) |
| 46 Mio. Entscheidungen ≈ 35 Tage Spielzeit | `models/space_pirate_bot.json`; 46 Mio. × 2 Bilder ÷ 30 Bilder/s |
| etwa anderthalb Tage Rechenzeit | [Lerntagebuch 12](../lernen/12_phase12_generalist_schueler.md) und [13](../lernen/13_phase13_links.md) (Schätzung) |
| 14 Stufen, neue Stufe ab 60 % | `jumpnrun/levelgen/generator.py`, `jumpnrun/rl/curriculum.py` |
| Gruben ohne Tod, Spielzeit an der Uhr, 19.000 Bilder/s | [Lerntagebuch 1](../lernen/01_phase0_spielkern.md) |
| erster Bot: 0 → 32 von 32, 25 Minuten, Dauerhüpfen, Zitat zur Zusatzregel | [Lerntagebuch 2](../lernen/02_phase1_erster_bot.md) |
| 174 Gegner, keiner abgeschossen | [Lerntagebuch 3](../lernen/03_phase2_gegner.md) |
| 99 von 120, aber 0 von 32 in der Prüfung | [Lerntagebuch 4](../lernen/04_phase3_pruefung.md) |
| 28 Abschüsse, 64 bzw. 114 von 120 | [Lerntagebuch 5](../lernen/05_phase5_abschauen.md) |
| heutiger Bot hat zuerst beim Löser abgeschaut | [Lerntagebuch 12](../lernen/12_phase12_generalist_schueler.md) („BC-Start“), `jumpnrun/rl/bc12.py` |
| Wand hinter der Kiste, 17 von 27 Fehlversuchen | [Lerntagebuch 6](../lernen/06_phase6_generalist.md), [7](../lernen/07_phase7_zwei_wege.md) |
| Umkehren wurde nicht belohnt, Weg-Belohnung | [Lerntagebuch 9](../lernen/09_phase9_umkehren.md) |
| Lernkurve auf dem Prüfungslevel | `docs/medien/pruefung_messung.json`; Phase 8 mit 256 Versuchen (252 von 256): `docs/lernen/daten/phase12_diagnose/diagnose_p8_T0.3.json` |

## Weiterführend

- **Live zeigen, ohne Installation:** die Web-App <https://leonvdetten.github.io/2D_JumpNRun/> im Browser öffnen
  (Fenster im Querformat; Maus und Tastatur gehen auch am Beamer-Rechner). „Bot zuschauen“ → Reiter „Prüfung“ →
  „Das Prüfungslevel“; unter „Gegen den Bot“ treten Schülerinnen und Schüler selbst an. Mehr in
  [Die Web-App](../mobile.md).
- **Live zeigen mit Python:** das Projekt von GitHub laden, `pip install -r requirements.txt` (lädt u. a. PyTorch),
  dann `python spacepirate.py` (Modus „Gegen den Bot“) oder
  `python -m jumpnrun.rl.watch --level levels/exam/level.txt --live`. Mehr in [Spielen](../spielen.md) und
  [Der Bot](../bot.md).
- **Videos:** [`bot_pruefung_2023.mp4`](../medien/bot_pruefung_2023.mp4) (ganzer Lauf) und
  [`bot_lernfortschritt.mp4`](../medien/bot_lernfortschritt.mp4) (Phase 1 bis 13).
- **Vertiefung:** das [Lerntagebuch](../lernen/00_ueberblick.md) und das interaktive Notebook
  ([HTML-Lesefassung](../lernen/projekt_interaktiv.html)).
- **Selbst ausprobieren** (Python; vorher `pip install stable-baselines3`, bringt Gymnasium mit): Ein Bot lernt in
  wenigen Zeilen, einen Stab zu balancieren. Im Protokoll steigt `ep_rew_mean` (mittlerer Return); 500 ist das
  Maximum, dann wurde der Stab bis zum Ende gehalten:

  ```python
  import gymnasium as gym
  from stable_baselines3 import PPO

  env = gym.make("CartPole-v1")
  model = PPO("MlpPolicy", env, verbose=1).learn(total_timesteps=50_000)
  ```

## Die Seite anpassen

- Die Datei lässt sich mit jedem Texteditor bearbeiten. Regeln: kein `style`, kein `<script>`; in `<pre>`-Gittern
  nur ASCII-Zeichen, gleich lange Zeilen und höchstens 30 Zeichen Breite (sonst scrollt die Seite auf dem Handy
  seitwärts); jede Türgruppe bekommt ihren eigenen `name`; Sprungziele (`id`) nie in zugeklappte `<details>` legen.
- Das GIF steckt als Daten-URI im `srcset` des einzigen `<img>`, eine sehr lange Zeile. `sizes` verkleinert es auf
  schmalen Bildschirmen, das `src` davor ist nur ein 1×1-Platzhalter. Wer die Datei kleiner braucht (dann etwa
  30 KB), löscht das `<figure>` um das Bild; die Seite funktioniert ohne Bild.
- Das GIF wurde aus dem README-Video erzeugt (ffmpeg, nur zum Neuerzeugen nötig, im Projektordner ausführen):

  ```bash
  ffmpeg -ss 0.4 -t 14 -i docs/medien/bot_pruefung_2023.mp4 -filter_complex \
    "setpts=PTS/2,fps=10,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
    -loop 0 bot_pruefung_480.gif
  ```

- Prüfen lässt sich die Datei mit dem [W3C-Validator](https://validator.w3.org/nu/) (Datei hochladen).

## Lizenz

Seite und Code: MIT, © 2023–2026 Leon von Detten. Für den Unterricht frei verwendbar und veränderbar. Die
Grafiken im GIF sind freie Assets mit eigenen Lizenzen: Pirat von Craftpix, Gegner von Pipoya, Blöcke von
PNG Wing, Kiste von Admurin (Links in der [README](../../README.md#credits--lizenz)).
