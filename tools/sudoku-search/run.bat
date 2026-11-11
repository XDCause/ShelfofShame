@echo off
REM The sudoku search: see README.txt. Close this window (or Ctrl+C) to stop - found.tsv keeps what it found.
cd /d "%~dp0"
where node >nul 2>nul || (echo Node.js isn't installed - get the LTS version from https://nodejs.org, then run this again. & pause & exit /b 1)
node search.mjs %*
pause
