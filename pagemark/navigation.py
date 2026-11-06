"""Compatibility import; implementation lives in pagemark_core."""
import sys
from pagemark_core import navigation as _implementation

sys.modules[__name__] = _implementation
