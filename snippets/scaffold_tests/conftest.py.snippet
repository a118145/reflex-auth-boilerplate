"""Shared test setup.

**A Reflex deprecation fails the tests.** Reflex (0.11) reports a deprecated
API only as a record of the ``reflex.deprecation`` logger, once per call site
and process — not as a Python warning — and pytest hides log records. A test
could use a deprecated API and stay green.

The handler is attached before any test module imports the app, so a
deprecated API used at import time is caught too. It raises at the call
site, so the failing test names the culprit; a deprecation a caller swallowed
still fails the session at the end. ``test_deprecations.py`` checks the
guard. ``scripts/check.sh --full`` covers the other path, ``reflex compile``.

Put shared fixtures below the guard, and import the app only after it.
"""

import logging

import pytest


class ReflexDeprecationError(Exception):
    """A deprecated Reflex API was used. The message is Reflex's own."""


# Every deprecation seen, also those a caller swallowed: checked at the end.
REFLEX_DEPRECATIONS: list[str] = []


class _FailOnDeprecation(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        REFLEX_DEPRECATIONS.append(message)
        raise ReflexDeprecationError(message)


logging.getLogger("reflex.deprecation").addHandler(_FailOnDeprecation(logging.WARNING))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    # Reflex reports each deprecation once per process; one raised where an
    # exception is caught would otherwise pass unnoticed.
    if REFLEX_DEPRECATIONS:
        print("\nReflex deprecations:\n" + "\n".join(REFLEX_DEPRECATIONS))
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
