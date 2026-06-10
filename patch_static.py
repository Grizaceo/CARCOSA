#!/usr/bin/env python3
"""Patch game_server.py to serve static files."""
import sys

sys.path.insert(0, '/app')

with open('/app/sim/game_server.py', 'r') as f:
    content = f.read()

if 'StaticFiles' not in content:
    # Add import
    content = content.replace(
        'from fastapi import FastAPI, HTTPException, WebSocket',
        'from fastapi import FastAPI, HTTPException, WebSocket\nfrom fastapi.staticfiles import StaticFiles'
    )
    # Mount static files
    content = content.replace(
        'app = FastAPI(title="CARCOSA Game Server", version="1.0.0")',
        '''app = FastAPI(title="CARCOSA Game Server", version="1.0.0")

# Servir frontend estático en /
app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")'''
    )

    with open('/app/sim/game_server.py', 'w') as f:
        f.write(content)
    print("Patched game_server.py for static file serving")
else:
    print("Already patched")