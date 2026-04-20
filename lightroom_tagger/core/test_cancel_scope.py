"""Tests for the cancel scope thread-local registry."""

from __future__ import annotations

import threading
import time

import pytest

from lightroom_tagger.core import cancel_scope


def test_no_scope_is_not_cancelled():
    cancel_scope.clear()
    assert cancel_scope.is_cancelled() is False


def test_install_toggles_flag():
    cancel_scope.clear()
    flag = {"cancel": False}
    with cancel_scope.install(lambda: flag["cancel"]):
        assert cancel_scope.is_cancelled() is False
        flag["cancel"] = True
        assert cancel_scope.is_cancelled() is True
    # Scope exited — back to default.
    assert cancel_scope.is_cancelled() is False


def test_nested_scopes_restore_previous():
    cancel_scope.clear()
    outer_called = []
    inner_called = []
    with cancel_scope.install(lambda: outer_called.append(1) or False):
        with cancel_scope.install(lambda: inner_called.append(1) or False):
            cancel_scope.is_cancelled()
        # Outer should be active again after inner exits.
        cancel_scope.is_cancelled()
    assert len(outer_called) == 1
    assert len(inner_called) == 1


def test_scope_is_per_thread():
    cancel_scope.clear()
    result_main = []
    result_worker = []

    def worker():
        # Worker thread has no scope of its own.
        result_worker.append(cancel_scope.is_cancelled())

    with cancel_scope.install(lambda: True):
        result_main.append(cancel_scope.is_cancelled())
        t = threading.Thread(target=worker)
        t.start()
        t.join()

    assert result_main == [True]
    assert result_worker == [False]


def test_broken_callback_is_swallowed():
    cancel_scope.clear()

    def raises():
        raise RuntimeError("broken")

    with cancel_scope.install(raises):
        # Must not propagate — callers would rather keep processing than
        # crash the whole job on a bad callback.
        assert cancel_scope.is_cancelled() is False
