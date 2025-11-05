"""
Vercel API Handler for Telegram Affiliate Publisher

This file serves as the entry point for Vercel serverless deployment.
Handles missing environment variables gracefully.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path for Vercel
current_dir = Path(__file__).parent.parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

# Set default environment variables if not present (for Vercel deployment)
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:///temp.db'  # Fallback for health checks

if 'ADMIN_USERNAME' not in os.environ:
    os.environ['ADMIN_USERNAME'] = 'admin'

if 'ADMIN_PASSWORD' not in os.environ:
    os.environ['ADMIN_PASSWORD'] = 'changeme123'

# Import the FastAPI app after setting defaults
try:
    from interfaces.api.main import app
except Exception as e:
    # If import fails, create a minimal app for health checks
    from fastapi import FastAPI
    app = FastAPI()
    print(f"Warning: Failed to import main app: {e}")

    @app.get("/")
    async def root():
        return {"message": "Telegram Affiliate Publisher API - Initializing", "status": "starting"}

    @app.get("/health")
    async def health():
        return {
            "status": "initializing",
            "message": "Application is starting up",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0.0",
            "service": "telegram-affiliate-publisher"
        }

# Export the app for Vercel
# Vercel expects the ASGI app to be available as a module-level variable
