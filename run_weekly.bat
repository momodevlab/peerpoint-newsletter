@echo off
:: PeerPoint Market Wire — Weekly Newsletter Runner
:: Run this manually or schedule it via Windows Task Scheduler.
:: Generates the full newsletter and uploads a draft to Substack.

set PYTHON=C:\Users\aprud\AppData\Local\Programs\Python\Python312\python.exe
set DIR=C:\Users\aprud\OneDrive\Desktop\Newsletter

cd /d %DIR%

echo [1/7] Fetching rate data...
%PYTHON% tools/research_rates.py
if %errorlevel% neq 0 ( echo ERROR in research_rates.py && exit /b 1 )

echo [2/7] Generating charts...
%PYTHON% tools/create_infographics.py
if %errorlevel% neq 0 ( echo ERROR in create_infographics.py && exit /b 1 )

echo [3/7] Researching this week's news...
%PYTHON% tools/research_perplexity.py
if %errorlevel% neq 0 ( echo ERROR in research_perplexity.py && exit /b 1 )

echo [4/7] Writing newsletter content...
%PYTHON% tools/generate_newsletter.py
if %errorlevel% neq 0 ( echo ERROR in generate_newsletter.py && exit /b 1 )

echo [5/7] Assembling HTML...
%PYTHON% tools/assemble_html.py
if %errorlevel% neq 0 ( echo ERROR in assemble_html.py && exit /b 1 )

echo [6/7] Generating social posts...
%PYTHON% tools/generate_social_posts.py
if %errorlevel% neq 0 ( echo ERROR in generate_social_posts.py && exit /b 1 )

echo [7/7] Posting to Slack for review...
%PYTHON% tools/send_to_slack.py
if %errorlevel% neq 0 ( echo ERROR in send_to_slack.py && exit /b 1 )

echo.
echo Done. Check Slack for newsletter, LinkedIn post, and tweets.
