@echo off
:: Sätt källa och mål med korta 8.3-namn för att undvika åäö-problem
set "SOURCE_USER=C:\Users\TORBJÖ~1"
set "TARGET_USER=C:\Users\torbjorn"

:: Kopiera VS Code-inställningar
xcopy "%SOURCE_USER%\.vscode" "%TARGET_USER%\.vscode" /E /I /Y

:: Kopiera projektmapp
xcopy "%SOURCE_USER%\smartweb" "%TARGET_USER%\smartweb" /E /I /Y

:: Starta VS Code med arbetsytan
code "%TARGET_USER%\smartweb\runerova.code-workspace"
