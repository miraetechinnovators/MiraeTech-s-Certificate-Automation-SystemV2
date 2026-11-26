@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add Python to PATH". & pause & exit /b 1)
if not exist .venv (
  echo First run: setting things up, this takes a minute...
  python -m venv .venv || (echo Could not create environment & pause & exit /b 1)
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -r requirements.txt || (echo Install failed - check your internet & pause & exit /b 1)
)
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  mkdir "%USERPROFILE%\.streamlit" 2>nul
  (echo [general]& echo email = "") > "%USERPROFILE%\.streamlit\credentials.toml"
)
.venv\Scripts\python -m streamlit run app.py
pause
