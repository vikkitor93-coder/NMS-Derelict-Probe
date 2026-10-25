@echo off
rem On-demand map server for the public atlas site. Listens on 127.0.0.1:8791 ONLY (not reachable from the network
rem until you start a tunnel, see EXPOSE.md). Keep this window open; press Ctrl+C to stop. Logs aggregate counts only.
title NMS on-demand map server (127.0.0.1:8791)
cd /d "%~dp0.."
python -I ondemand\ondemand_server.py %*
pause
