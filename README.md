# Anki-speech

This script reads an Anki package file (*.apkg), finds all notes which do not have sound file attached to the front side of the note, then generates the sound file using Google Text-to-Speech API and saves everything back to the package. So basically if you have a deck with thousands of text cards, you can voice them all in one go: export, run the script, then import back and sync.

Existing libraries working with Anki decks turned out to be difficult to use or broken, so I just access the notes directly, as a sqlite database, it's pretty straightforward.

If you use this script, make backup first.