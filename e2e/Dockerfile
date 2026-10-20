# The browser walk-through's image: Playwright's own (browsers + system libraries) with the matching
# Python package installed once, instead of on every run. run_e2e.ps1 builds it (cached after that).
# axe-playwright-python brings axe-core (axe.min.js), the accessibility checker ui_audit.py injects.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
RUN pip install --no-cache-dir --disable-pip-version-check playwright==1.47.0 axe-playwright-python==0.1.8
