"""CDP façade over the ``browser-harness`` CLI (stdin Python snippets).

Phase 17: convenience wrapper for E2E tests; uses browser-harness only (D-07).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time


class BrowserSession:
    """Thin sync wrapper around ``browser-harness`` primitives."""

    def __init__(self) -> None:
        self._exe = shutil.which("browser-harness")
        if self._exe is None:
            raise RuntimeError(
                "browser-harness not found on PATH; install it and verify with "
                "browser-harness --doctor"
            )

    def _run(
        self,
        script: str,
        *,
        timeout: float = 120.0,
        decode_stdout: bool = False,
    ) -> str:
        proc = subprocess.run(
            [self._exe],
            input=script,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if proc.returncode != 0:
            out_tail = (proc.stdout or "")[-2048:]
            err_tail = (proc.stderr or "")[-2048:]
            raise RuntimeError(
                "browser-harness process failed with non-zero return code "
                f"{proc.returncode}; stdout={out_tail!r} stderr={err_tail!r}"
            )
        stdout = proc.stdout or ""
        if not decode_stdout:
            return stdout
        prefix = "__E2E_OUT__"
        for line in stdout.splitlines():
            if line.startswith(prefix):
                return json.loads(line[len(prefix) :])
        raise RuntimeError(
            "browser-harness stdout missing __E2E_OUT__ payload; "
            f"got stdout={stdout[-2048:]!r}"
        )

    def navigate(self, url: str) -> None:
        script = "new_tab(" + json.dumps(url) + ")\nwait_for_load()\n"
        self._run(script, timeout=120.0)

    def get_text(self, css_selector: str) -> str:
        code = (
            "return document.querySelector("
            + json.dumps(css_selector)
            + ")?.innerText || \"\""
        )
        script = (
            "import json\n"
            f"text = js({code!r})\n"
            'print("__E2E_OUT__" + json.dumps(text))\n'
        )
        return self._run(script, timeout=120.0, decode_stdout=True)

    def wait_for(self, css_selector: str, *, timeout_seconds: float = 30.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        code = (
            "return document.querySelector("
            + json.dumps(css_selector)
            + ") !== null"
        )
        script = (
            "import json\n"
            f"found = js({code!r})\n"
            'print("__E2E_OUT__" + json.dumps(bool(found)))\n'
        )
        while time.monotonic() < deadline:
            found = self._run(script, timeout=120.0, decode_stdout=True)
            if found:
                return
            time.sleep(0.25)
        raise TimeoutError(f"timeout waiting for {css_selector!r}")

    def click(self, css_selector: str) -> None:
        code = (
            "return JSON.stringify((function() {\n"
            "  const el = document.querySelector("
            + json.dumps(css_selector)
            + ");\n"
            "  if (!el) { throw new Error('element not found for selector'); }\n"
            "  const r = el.getBoundingClientRect();\n"
            "  return [Math.floor(r.left + r.width / 2), "
            "Math.floor(r.top + r.height / 2)];\n"
            "})())"
        )
        script = (
            "import json\n"
            f"raw = js({code!r})\n"
            "pair = json.loads(raw) if isinstance(raw, str) else raw\n"
            "x, y = int(pair[0]), int(pair[1])\n"
            "click(x, y)\n"
            "wait_for_load()\n"
        )
        self._run(script, timeout=120.0)

    def close(self) -> None:
        # Phase 17: teardown via browser-harness daemon lifecycle; no explicit close.
        pass
