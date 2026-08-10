"""PlantWijs backend-package.

Importeren van dit package doet bewust geen netwerk-calls en laadt geen datasets;
alles wordt lazy geladen bij het eerste gebruik.
"""

from .config import VERSION

__version__ = VERSION

__all__ = ["VERSION", "__version__"]
