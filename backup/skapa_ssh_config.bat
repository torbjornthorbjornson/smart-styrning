@echo off
SETLOCAL

:: Skapa .ssh-mappen om den inte finns
IF NOT EXIST "%USERPROFILE%\.ssh" (
    mkdir "%USERPROFILE%\.ssh"
)

:: Skriv SSH-konfigurationen till config-filen
> "%USERPROFILE%\.ssh\config" echo Host pi
>> "%USERPROFILE%\.ssh\config" echo     HostName raspberrypi
>> "%USERPROFILE%\.ssh\config" echo     User runerova
>> "%USERPROFILE%\.ssh\config" echo     IdentityFile ~/.ssh/id_ed25519

echo SSH-konfig skapad i %USERPROFILE%\.ssh\config
pause