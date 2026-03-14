# Re-export settings so that `from app.config import settings` continues to work
# even though app/config/ is now a package (which shadows app/config.py).
import importlib.util as _util
import os as _os

# Load the sibling config.py directly to avoid infinite recursion
_config_path = _os.path.normpath(
    _os.path.join(_os.path.dirname(__file__), "..", "config.py")
)
_spec = _util.spec_from_file_location("_app_config_module", _config_path)
_mod = _util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

settings = _mod.settings
Settings = _mod.Settings
