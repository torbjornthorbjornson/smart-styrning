@echo off
echo 🔄 Kopierar VS Code-inställningar från "Torbjörn" till "torbjorn"...

set OLDUSER=C:\Users\Torbjörn
set NEWUSER=C:\Users\torbjorn

:: Skapa målmapp om den inte finns
if not exist "%NEWUSER%\AppData\Roaming\Code\User" (
    mkdir "%NEWUSER%\AppData\Roaming\Code\User"
)

:: Kopiera settings.json och keybindings.json
xcopy "%OLDUSER%\AppData\Roaming\Code\User\settings.json" "%NEWUSER%\AppData\Roaming\Code\User\" /Y
xcopy "%OLDUSER%\AppData\Roaming\Code\User\keybindings.json" "%NEWUSER%\AppData\Roaming\Code\User\" /Y

:: Kopiera snippets-mappen om den finns
xcopy "%OLDUSER%\AppData\Roaming\Code\User\snippets" "%NEWUSER%\AppData\Roaming\Code\User\snippets" /E /I /Y

:: Kopiera .vscode-mappen (extensions)
xcopy "%OLDUSER%\.vscode" "%NEWUSER%\.vscode" /E /I /Y

:: Kopiera projektmappen smartweb från Dokument till Desktop
xcopy "%OLDUSER%\Documents\smartweb" "%NEWUSER%\Desktop\smartweb" /E /I /Y

echo ✅ Klart! Kolla på nya kontot så allt är på plats.
pause
