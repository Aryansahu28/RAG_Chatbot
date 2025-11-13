"""Backward compatible module to retain Flask entry point imports.

The backend has transitioned to FastAPI. Import the FastAPI application
instance from `src.app` to keep existing scripts that refer to
`flaskAPI.index:app` functioning.
"""

from src.app import app  # noqa: F401