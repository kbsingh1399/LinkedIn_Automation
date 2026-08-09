@echo off
title LinkedIn Auto Agent - Background Loop
cd /d "C:\Users\SIGMA\Documents\LinkedIn_Automation"

:loop
echo ========================================================
echo 🚀 Launching LinkedIn Autonomous Agent at %time%
echo ========================================================
python LinkedIn_Auto_Agent.py --mode all

echo ========================================================
echo ✅ Cycle Complete. Sleeping for 2 hours (7200 seconds)...
echo Press Ctrl+C to stop the loop.
echo ========================================================
timeout /t 7200 /nobreak
goto loop
