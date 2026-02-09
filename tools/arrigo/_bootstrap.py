"""Bootstrap module to make smartweb project imports work when running from tools/arrigo.

These scripts are often executed with CWD=tools/arrigo (systemd/manual),
so we explicitly add the project root (smartweb/) to sys.path.

This keeps Arrigo tools decoupled from packaging/install steps.
"""

from __future__ import annotations

import os
import sys


def ensure_project_root_on_syspath() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    return project_root


ensure_project_root_on_syspath()
