"""
Run the pytest suite of the optimization module:  python -m optimization.run_tests [pytest args]

pytest itself calls platform.* at start-up, which hangs forever when the Windows WMI service is stuck (seen on
2026-10-28); disabling Python's _wmi helper first makes platform fall back to the registry (see __init__.py).
"""
import os
import sys

if os.environ.get("COMPOSITE_USE_WMI") != "1":
    sys.modules.setdefault("_wmi", None)

import pytest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    sys.exit(pytest.main(["-c", os.path.join(HERE, "pytest.ini"), "--rootdir", HERE,
                          os.path.join(HERE, "tests")] + sys.argv[1:]))
