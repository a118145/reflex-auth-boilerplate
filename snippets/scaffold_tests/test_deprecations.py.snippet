"""The deprecation guard in ``conftest.py`` works: Reflex only logs
deprecations, and the guard turns them into failures."""

import pytest
from reflex_base.utils import console

from .conftest import REFLEX_DEPRECATIONS, ReflexDeprecationError


def test_a_reflex_deprecation_fails_the_tests() -> None:
    with pytest.raises(ReflexDeprecationError, match="probe"):
        console.deprecate(
            feature_name="probe",
            reason="checks the guard",
            deprecation_version="0",
            removal_version="1",
            dedupe=False,
        )
    # Handled here; it must not fail the session at the end.
    REFLEX_DEPRECATIONS.remove(next(m for m in REFLEX_DEPRECATIONS if "probe" in m))
