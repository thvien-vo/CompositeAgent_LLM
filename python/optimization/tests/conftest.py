import os
import sys

import numpy as np
import pytest

PYTHON_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)


@pytest.fixture(scope="session")
def im7():
    from optimization.material import get_material
    return get_material("IM7/8552", verbose=False)


@pytest.fixture(scope="session")
def cfrp_ml():
    from ml import predict_material
    from optimization.material import Material
    return Material(**predict_material("CFRP"), name="CFRP (ML)")


@pytest.fixture
def rng():
    return np.random.default_rng(12345)
