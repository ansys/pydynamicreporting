from os.path import join

import numpy as np
import pytest

from ansys.dynamicreporting.core import ADR
from ansys.dynamicreporting.core.item import Image


@pytest.mark.ado_test
def test_create_img(adr_serverless_create, request) -> bool:
    ...
