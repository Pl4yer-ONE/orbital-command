#!/bin/bash
# ORBITAL COMMAND - Satellite Tracker Launcher
cd "$(dirname "$0")"
source venv/bin/activate
exec python3 main.py "$@"
