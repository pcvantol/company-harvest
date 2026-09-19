"""Company Harvest."""

import sys
from importlib.metadata import version

if sys.version_info[:2] != (3, 14):
    raise RuntimeError("Company Harvest vereist Python 3.14.x")

__version__ = version("company-harvest")

__all__ = ["__version__"]
