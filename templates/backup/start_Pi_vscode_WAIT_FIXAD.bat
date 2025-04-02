@echo off
REM Startar VS Code med workspace, men väntar in SSH-anslutning först

REM Startar VS Code men utan workspace (så vi kan koppla upp oss först)
start "" code

REM Vänta 5 sekunder så användaren hinner ansluta SSH
timeout /t 5 /nobreak > nul

REM Öppnar workspace efter anslutning
code "C:\Users\Torbjörn\Desktop\runerova_FIXAD.code-workspace"
