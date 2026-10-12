"""SPACE PIRATE
    The game app: loading screen, main menu, single player with best times, stars and ghost,
    race against the trained bot, random levels and the level editor.

    Usage:
            python spacepirate.py [path/to/level.txt] [--no-bot]

        author: Leon von Detten
        license: free
"""

import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

from jumpnrun.app.main import main

if __name__ == "__main__":
    main()
