"""Isolated controlled BOLA evaluation lab.

This package deliberately does not import VAmPI's application, models, or
configuration. It is a separate service used only for controlled experiments.
"""

from .server import create_app

__all__ = ["create_app"]
