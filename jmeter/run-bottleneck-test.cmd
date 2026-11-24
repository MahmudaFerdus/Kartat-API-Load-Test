@echo off
rem ==============================================================================
rem Bottleneck & Capacity Test Runner for 2-Core / 4GB RAM Target Server (Windows)
rem ==============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

if not defined JVM_ARGS (
  set "JVM_ARGS=-Xms1g -Xmx2g -XX:+UseG1GC -XX:+ParallelRefProcEnabled"
)

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

set "QENV="
if exist ".env" (
  set "QENV=-q .env"
) else if exist "..\.env" (
  set "QENV=-q ..\.env"
) else if exist "secrets.properties" (
  set "QENV=-q secrets.properties"
) else (
  echo Warning: Neither .env nor secrets.properties was found.
  echo Copy .env.example to .env and configure credentials before running.
)

call :MakeStamp
if errorlevel 1 (
  echo Could not build a yyyyMMdd-HHmmss folder name from date [%date%] and time [%time%].
  pause
  exit /b 1
)

set "N=0"
set "OUT=results\bottleneck-%STAMP%"
:newdir
if exist "%OUT%\" goto bump
mkdir "%OUT%"
if errorlevel 1 goto bump
goto rundir
:bump
set /a N+=1
if %N% GEQ 100 (
  echo Could not create a new results folder for %STAMP%.
  pause
  exit /b 1
)
set "OUT=results\bottleneck-%STAMP%-%N%"
goto newdir

:rundir
echo ==============================================================================
echo  Starting Bottleneck Stress Test
echo  Target Configuration: 2-Core CPU / 4GB RAM Server
echo  Results Directory:   %OUT%
echo ==============================================================================

call "%JMETER%" -n -t kartat-gateway-purchase.jmx -q results-format.properties %QENV% -l "%OUT%\results.jtl" -j "%OUT%\jmeter.log" -e -o "%OUT%\dashboard" %*
set "RC=%ERRORLEVEL%"

rem Generate comprehensive summary report
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python generate-summary.py "%OUT%"
) else (
  where python3 >nul 2>nul
  if %ERRORLEVEL%==0 (
    python3 generate-summary.py "%OUT%"
  )
)

if not "%RC%"=="0" pause
exit /b %RC%

:MakeStamp
setlocal EnableDelayedExpansion
set "T=!time: =0!"
if "!T:~1,1!"==":" set "T=0!T!"
if "!T:~1,1!"=="." set "T=0!T!"
set "HH=!T:~0,2!"
set "MN=!T:~3,2!"
set "SS=!T:~6,2!"
set "SEP1=!T:~2,1!"
set "SEP2=!T:~5,1!"

set "D=!date!"
set "D=!D:/= !"
set "D=!D:-= !"
set "D=!D:.= !"
set "PARTS="
for %%P in (!D!) do (
  set "TOK=%%P"
  set "DIGITS=1"
  for /f "delims=0123456789" %%N in ("!TOK!") do set "DIGITS=0"
  if "!DIGITS!"=="1" if defined TOK (
    if defined PARTS (set "PARTS=!PARTS! !TOK!") else set "PARTS=!TOK!"
  )
)

set "A="
set "B="
set "C="
for /f "tokens=1-3" %%a in ("!PARTS!") do (
  set "A=%%a"
  set "B=%%b"
  set "C=%%c"
)

set "ORDER=MDY"
for /f "tokens=1,3" %%I in ('reg query "HKCU\Control Panel\International" /v iDate 2^>nul ^| find "iDate"') do set "IDATE=%%J"
if "!IDATE!"=="1" set "ORDER=DMY"
if "!IDATE!"=="2" set "ORDER=YMD"
if defined A if not "!A:~3!"=="" if "!A:~4!"=="" set "ORDER=YMD"
if "!ORDER!"=="MDY" if defined A if 1!A! GTR 112 set "ORDER=DMY"
if "!ORDER!"=="DMY" if defined B if 1!B! GTR 112 set "ORDER=MDY"

if "!ORDER!"=="YMD" (
  set "YYYY=!A!"
  set "MM=!B!"
  set "DD=!C!"
) else if "!ORDER!"=="DMY" (
  set "DD=!A!"
  set "MM=!B!"
  set "YYYY=!C!"
) else (
  set "MM=!A!"
  set "DD=!B!"
  set "YYYY=!C!"
)

if defined MM if "!MM:~1!"=="" set "MM=0!MM!"
if defined DD if "!DD:~1!"=="" set "DD=0!DD!"
if defined HH if "!HH:~1!"=="" set "HH=0!HH!"

set "BAD="
if not defined YYYY set "BAD=1"
if not defined MM set "BAD=1"
if not defined DD set "BAD=1"
if not defined HH set "BAD=1"
if not defined MN set "BAD=1"
if not defined SS set "BAD=1"
if not "!SEP1!"==":" if not "!SEP1!"=="." set "BAD=1"
if not "!SEP2!"==":" if not "!SEP2!"=="." set "BAD=1"
for %%V in (!YYYY! !MM! !DD! !HH! !MN! !SS!) do (
  for /f "delims=0123456789" %%N in ("%%V") do set "BAD=1"
)
if "!YYYY:~4!" NEQ "" set "BAD=1"
if "!YYYY:~3!"=="" set "BAD=1"
if "!MM:~2!" NEQ "" set "BAD=1"
if "!MM:~1!"=="" set "BAD=1"
if "!DD:~2!" NEQ "" set "BAD=1"
if "!DD:~1!"=="" set "BAD=1"
if "!HH:~2!" NEQ "" set "BAD=1"
if "!HH:~1!"=="" set "BAD=1"
if "!MN:~2!" NEQ "" set "BAD=1"
if "!MN:~1!"=="" set "BAD=1"
if "!SS:~2!" NEQ "" set "BAD=1"
if "!SS:~1!"=="" set "BAD=1"
if defined BAD goto stamp_fail
if 1!MM! LSS 101 set "BAD=1"
if 1!MM! GTR 112 set "BAD=1"
if 1!DD! LSS 101 set "BAD=1"
if 1!DD! GTR 131 set "BAD=1"
if 1!HH! GTR 123 set "BAD=1"
if 1!MN! GTR 159 set "BAD=1"
if 1!SS! GTR 159 set "BAD=1"
if defined BAD goto stamp_fail

set "STAMP=!YYYY!!MM!!DD!-!HH!!MN!!SS!"
endlocal & set "STAMP=%STAMP%" & exit /b 0

:stamp_fail
endlocal
exit /b 1
