"""Development utilities for notebook workflows.

Provides functions to easily reload modules and import common components
for interactive development in Jupyter notebooks.
"""

import importlib
import sys
import types


def reload_module_recursive(module: types.ModuleType) -> None:
    """Recursively reload a module and all its submodules.

    Args:
        module: The module to reload.

    """
    # Reload the main module first
    importlib.reload(module)

    # Get the module name prefix
    module_prefix = module.__name__ + "."

    # Find and reload all submodules
    submodules = [
        (name, mod)
        for name, mod in sys.modules.items()
        if isinstance(mod, types.ModuleType) and name.startswith(module_prefix)
    ]

    # Sort by name length (reload parent modules before child modules)
    submodules.sort(key=lambda x: x[0].count("."))

    for name, mod in submodules:
        try:
            importlib.reload(mod)
        except Exception as e:  # noqa: BLE001
            print(f"Failed to reload {name}: {e}")  # noqa: T201
