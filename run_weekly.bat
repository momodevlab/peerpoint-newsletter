@echo off
:: PeerPoint Market Wire — Weekly Newsletter Runner
:: Run this manually or schedule it via Windows Task Scheduler.
:: Generates the full newsletter and uploads a draft to Substack.

set PYTHON=C:\Users\aprud\AppData\Local\Programs\Python\Python312\python.exe
set DIR=C:\Users\aprud\OneDrive\Desktop\Newsletter

cd /d %DIR%

echo [1/5] Fetching rate data...
%PYTHON% tools/research_rates.py
if %errorlevel% neq 0 ( echo ERROR in research_rates.py && exit /b 1 )

echo [2/5] Generating charts...
%PYTHON% tools/create_infographics.py
if %errorlevel% neq 0 ( echo ERROR in create_infographics.py && exit /b 1 )

echo [3/5] Researching this week's news...
%PYTHON% tools/research_perplexity.py
if %errorlevel% neq 0 ( echo ERROR in research_perplexity.py && exit /b 1 )

echo [4/5] Writing newsletter content...
%PYTHON% tools/generate_newsletter.py
if %errorlevel% neq 0 ( echo ERROR in generate_newsletter.py && exit /b 1 )

echo [5/5] Assembling HTML...
%PYTHON% tools/assemble_html.py
if %errorlevel% neq 0 ( echo ERROR in assemble_html.py && exit /b 1 )

echo Uploading draft to Substack...
%PYTHON% tools/publish_substack.py
if %errorlevel% neq 0 ( echo ERROR in publish_substack.py && exit /b 1 )

echo.
echo Done. Review your draft at:
echo   https://peerpointcapital.substack.com/publish/posts
