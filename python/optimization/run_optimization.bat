@echo off
REM ==========================================================================
REM  run_optimization.bat - Layer 1: stacking sequence optimization (no LLM)
REM    run_optimization.bat           tests + all experiments (about 1.5 hours, at most 4 processes)
REM    run_optimization.bat --quick   tests + short experiments (fewer seeds, smaller budgets)
REM  Results: deliverables\optimization\results\*.csv, *.json, tables.md; figures\*.png
REM           (--quick writes to results_quick\ and figures_quick\ instead)
REM ==========================================================================
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0.."

echo === pytest (CLT, criteria, buckling, rules, repair, algorithms, material, MATLAB) ===
"%~dp0..\..\venv\Scripts\python.exe" -m optimization.run_tests -q -rs
if errorlevel 1 (
    echo TESTS FAILED - experiments not started.
    exit /b 1
)

"%~dp0..\..\venv\Scripts\python.exe" -m optimization.experiments.run_all %*
"%~dp0..\..\venv\Scripts\python.exe" -m optimization.experiments.make_tables %*
echo.
echo Done. See deliverables\optimization\
