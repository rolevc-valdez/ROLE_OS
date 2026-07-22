@echo off
set /p SOURCE=ChatGPT export ZIP or folder: 
set /p OUTPUT=ROLE_KNOWLEDGE_OS destination folder: 
python builder.py "%SOURCE%" "%OUTPUT%" --clean
pause
