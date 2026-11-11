The sudoku search - for the desktop PC
=====================================

It hunts for the hardest sudokus it can make, for Off the Clock's weekly puzzle. It uses all but one of the
PC's threads (a Ryzen 7 5700X: 15 of 16) and can run overnight or for days. The graphics card isn't used:
this is branchy, step-by-step solving, which graphics cards are bad at.

1. Install Node.js (the LTS version) from https://nodejs.org - the normal installer, all defaults.

2. Copy this whole folder (sudoku-search) to the desktop PC, e.g. to C:\sudoku-search.

3. Double-click run.bat. A window opens and says what it's doing every 3 minutes:
       21:40:12  30 min · 1,204,331 tried · best score 1312 · by tier {"1":2000} · saved to found.tsv
   Scores: 1000-1999 = tier 1 (very hard, like the app's own list today), 2000+ = tier 2 (the level of the
   famous "world's hardest" puzzles), 3000+ = tier 3 (nested trials). Tier 2 is the goal - it may take
   many hours, and it isn't guaranteed.

   To stop: close the window or press Ctrl+C. Nothing is lost - found.tsv is saved every 3 minutes.
   To run for a set time instead: open a command prompt in the folder and type   node search.mjs --hours 10
   To keep the PC usable: node search.mjs --threads 8

   Running it again carries on from found.tsv.

4. Bring found.tsv back to the laptop (a USB stick, Google Drive, or over Tailscale) and put it in
       C:\Users\xdhar\hobby-inventory\data\sudoku\found.tsv
   then, in that folder in PowerShell:
       .\load-sudoku-library.ps1 -File data\sudoku\found.tsv -List weekly
   The weekly puzzle then comes from the search's finds (hardest first, a week at a time).
   (Or just tell Claude it's there.)

Files: search.mjs (the search), engine.js (a copy of the app's sudoku engine - the search's own, so the app
changing doesn't change a running search), seeds.tsv (the app's own hardest puzzles to start from),
run.bat (starts it), found.tsv (what it finds - made by the search).
