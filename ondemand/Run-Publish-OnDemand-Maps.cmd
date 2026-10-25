@echo off
rem Publishes the maps visitors asked for (ondemand cache) to the atlas: views/ondemand/<REGION>.json.gz, plain fast-forward push,
rem at most one push per 30 minutes. Run it by hand or as a scheduled task. Does nothing when there is nothing new.
cd /d "%~dp0.."
python -I tools\publish_ondemand_maps.py --push
pause
