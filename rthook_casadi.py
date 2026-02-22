# Runtime hook: add casadi's directory to Windows DLL search path.
#
# _casadi.pyd depends on sibling DLLs (e.g. casadi_nlpsol_*.dll) that Windows
# won't find automatically unless their directory is explicitly registered.
# This hook runs before any imports, so the DLLs are found when casadi loads.

import os
import sys

if hasattr(sys, "_MEIPASS") and hasattr(os, "add_dll_directory"):
    # Add both the bundle root and the casadi subfolder
    os.add_dll_directory(sys._MEIPASS)
    casadi_dir = os.path.join(sys._MEIPASS, "casadi")
    if os.path.isdir(casadi_dir):
        os.add_dll_directory(casadi_dir)
