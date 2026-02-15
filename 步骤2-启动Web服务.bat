@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set CONDA_ENV_NAME=manga-env
set MINICONDA_DIR=%USERPROFILE%\miniconda3

if exist "%MINICONDA_DIR%\Scripts\activate.bat" (
  call "%MINICONDA_DIR%\Scripts\activate.bat" "%CONDA_ENV_NAME%"
)

python -m manga_translator web
