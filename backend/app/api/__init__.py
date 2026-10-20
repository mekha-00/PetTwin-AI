"""API package: routers are registered by ``app.main``."""

from app.api import auth, pets, users

__all__ = ["auth", "users", "pets"]
