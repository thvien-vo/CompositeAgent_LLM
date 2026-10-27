@echo off
REM ==========================================================================
REM  run_optimization.bat - Layer 1: stacking sequence optimization (no LLM)
REM    run_optimization.bat           tests + all experiments (about 1 hour)
REM    run_optimization.bat --quick   tests + short experiments (a few minutes)
REM  Results: deliverables\optimization\results\*.csv, figures\*.png
REM ==========================================================================
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0.."

echo === pytest (CLT, criteria, buckling, rules, repair, algorithms, material, MATLAB) ===
"%~dp0..\..\venv\Scripts\python.exe" -m pytest -q optimization\tests -c optimization\pytest.ini
if errorlevel 1 (
    echo TESTS FAILED - experiments not started.
    exit /b 1
)

"%~dp0..\..\venv\Scripts\python.exe" -m optimization.experiments.run_all %*
echo.
echo Done. See deliverables\optimization\
