@echo off
setlocal
cd /d "%~dp0"

if defined JMETER_HOME (
  set "JMETER=%JMETER_HOME%\bin\jmeter.bat"
) else (
  set "JMETER=jmeter.bat"
)

if defined JMETER_HOME if not exist "%JMETER_HOME%\bin\jmeter.bat" (
  echo Set JMETER_HOME to your Apache JMeter directory. bin\jmeter.bat was not found.
  pause
  exit /b 1
)

if not exist "secrets.properties" (
  echo secrets.properties is missing. Copy secrets.properties.example and set client_id, client_secret, and password.
)

set "QSECRETS="
if exist "secrets.properties" set "QSECRETS=-q secrets.properties"

call "%JMETER%" -t kartat-gateway-purchase.jmx -q results-format.properties -q load-180-purchases-60-seconds.properties %QSECRETS% %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
