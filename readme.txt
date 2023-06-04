Space Pirate

Spielbeschreibung:

Das Spiel Space Pirate ist ein 2D-Spiel, in welchem ein Pirat gesteuert wird.
Der Pirat muss sich durch ein Level kämpfen und dabei Gegner besiegen und Hindernisse überwinden.
Gegner können durch einen Sprung auf den Kopf oder durch einen Revolverschuss besiegt werden.
Das Spiel ist in Python geschrieben und verwendet die Pygame-Bibliothek.
Das Ziel ist es das Level zu beenden, indem die Kiste am Ende des Levels geöffnet wird.
Sobald das Level beendet ist, wird die benötigte Zeit ausgegeben.

Bitte beachten Sie, dass es sich bei diesem Spiel um einen Prototyp handelt,
welcher noch kein Game Over Screen oder Menü enthält. 
Des weiteren existiert lediglich ein Level. Dieses kann jedoch beliebig bearbeitet werden.
Das Level wird verändert, indem die level.txt Datei bearbeitet wird.
Hierbei müssen ASCII Zeichen verwendet werden, um die verschiedenen Objekte zu platzieren:
E = Enemy (Gegner)
B = Block
C = Chest (Kiste)
Es können mehrere Kisten in der Welt platziert werden. In diesem Fall dient jede Kiste als 
Endpunkt und das Spiel wird nach Öffnen dieser Kiste beendet.


Anforderungen:

Siehe requirement.txt Datei.


Installation:

Um die Applikation ausführen zu können, müssen die benötigten Bibliotheken heruntergeladen werden.
Für dieses Spiel werden die Pygame und Loguru Bibliotheken benötigt.
Diese können mit folgenden Befehlen heruntergeladen werden:
- pip install loguru==0.7.0
- pip install pygame==2.1.0

Außerdem wird Python3 benötigt. Diese Applikation wurde mit Python 3.9.13 entwickelt. 
Die Version kann auf der offiziellen Python-Seite heruntergeladen werden:
https://www.python.org/downloads/windows/


Ausführen des Spiels:

Um das Spiel zu starten, muss die Datei game.py ausgeführt werden.
Sobald das Spiel gestaret wird, öffnet sich ein neues Fenster und das Spiel beginnt.
Das Spiel kann lediglich durch das Schließen des Fensters beendet werden.
Sollte der Spieler durch einen Gegner eliminiert werden, beendet sich die Applikation automatisch.


Steuerung:

Der Piratenspieler kann mit den Tasten W, A, D, Leertaste und Enter gesteuert werden.
Die W-Taste und Leertaste führen einen Sprung aus.
Mit der A-Taste wird der Spieler nach links bewegt.
Mit der D-Taste wird der Spieler nach rechts bewegt.
Mit Enter führt der Spieler einen Revolverschuss aus.


Lizenzen:

Die verwenndeten Bilder (Sprites) sind Lizenzfrei und dürfen frei verwendet werden.
Die Bilder können auf folgenden Seiten heruntergeladen werden:

Player Spites: 
    https://craftpix.net/freebies/free-2d-pirate-character-sprites/

Enemy Sprites:
    https://pipoya.itch.io/pipoya-free-rpg-character-sprites-32x32

Block(Ground) Sprites:
    https://www.pngwing.com/en/free-png-zoola/download

Chest Sprites:
    https://admurin.itch.io/free-chest-animations


