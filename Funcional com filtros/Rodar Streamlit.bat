@echo off
REM ─────────────────────────────────────────────────────
REM Define code page UTF-8 para acentos
chcp 65001 > nul

REM ─────────────────────────────────────────────────────
REM Vai para a pasta do projeto
cd /d "%USERPROFILE%\OneDrive - Energisa\Área de Trabalho\BD\data\BD_funcional\Funcional com filtros"

REM ─────────────────────────────────────────────────────
REM Instala dependências
echo Instalando dependências...
"%USERPROFILE%\OneDrive - Energisa\Documentos\Python\Python310\Scripts\pip.exe" install ^
    streamlit ^
    streamlit-folium ^
    folium ^
    pandas ^
    branca ^
    numpy ^
    scipy ^
    matplotlib==3.6.3

REM ─────────────────────────────────────────────────────
REM Inicia o Streamlit com endereço e porta explícitos
echo Iniciando Streamlit…
"%USERPROFILE%\OneDrive - Energisa\Documentos\Python\Python310\python.exe" -m streamlit run ^
    "app.py" ^
    --server.address localhost ^
    --server.port 8501

pause
