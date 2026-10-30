@echo off
REM ==========================================================================
REM  run_demo.bat - demo 1 buoc cho buoi thuyet trinh (double-click hoac chay trong terminal)
REM    run_demo.bat                  demo day du: kiem tra -> agent (4 de) -> RAG (4 cau hoi) -> thiet ke (2 yeu cau)
REM    run_demo.bat --offline        khong co mang: chi dung Ollama gemma3:4b tren may
REM    run_demo.bat --parts 4        chi chay phan thiet ke tam bang loi (toi uu xep lop)
REM    run_demo.bat --interactive    sau demo, cho nguoi xem tu go de bai / yeu cau thiet ke / cau hoi
REM    run_demo.bat --no-wait        khong dung giua cac phan
REM    run_demo.bat --lang vi        LLM giai thich ket qua CLT bang tieng Viet
REM  Ket qua duoc luu them vao logs\demo_*.log
REM ==========================================================================
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0python"

tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
        echo Dang bat Ollama...
        start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
        timeout /t 8 /nobreak >nul
    )
)

"%~dp0venv\Scripts\python.exe" run_demo.py %*
echo.
echo Demo xong. Bam phim bat ky de dong cua so.
pause >nul
