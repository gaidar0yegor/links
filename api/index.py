"""
Vercel API Handler for Telegram Affiliate Publisher

This file serves as the entry point for Vercel serverless deployment.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path for Vercel
current_dir = Path(__file__).parent.parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

# Import the FastAPI app
from interfaces.api.main import app

# Export the app for Vercel
app = app

# Vercel expects the ASGI app to be available as a module-level variable
# The app is already defined in the imported module
