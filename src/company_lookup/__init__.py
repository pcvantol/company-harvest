"""Company Lookup."""

import sys
from importlib.metadata import version

if sys.version_info[:2] != (3, 14):
    raise RuntimeError("Company Lookup vereist Python 3.14.x")

__version__ = version("company-lookup")

__all__ = ["__version__"]
