@echo off
echo Startar VS Code med SSH till Pi...

timeout /t 3 >nul

code --folder-uri "vscode-remote://ssh-remote+pi/home/runerova/smartweb" --file-uri "vscode-remote://ssh-remote+pi/home/runerova/smartweb/runerova.code-workspace"
