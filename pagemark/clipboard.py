"""Compatibility import for the system clipboard adapter."""
import sys
from pagemark_platform import clipboard as _implementation

sys.modules[__name__] = _implementation
