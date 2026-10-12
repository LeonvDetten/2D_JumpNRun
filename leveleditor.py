"""LEVEL EDITOR
    Paint Space Pirate levels with the mouse, check that the bot can solve them, save them as level text.

    Usage:
            python leveleditor.py [path/to/level.txt]

    Without a file a new level is started. Press F1 in the editor for all controls.
"""

import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

from jumpnrun.editor.app import main

if __name__ == "__main__":
    main()
