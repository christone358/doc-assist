"""
CORS, authentication stubs and cross-origin configuration for development.
In production, set CORS origins to actual frontend domain.
"""

# This config is already applied in main.py via CORSMiddleware.
# For production, set ALLOWED_ORIGINS env var.

import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
