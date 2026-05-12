import pytest

pytestmark = pytest.mark.e2e

TITLE = "Lightroom Tagger"


def test_e2e_visualizer_homepage_smoke(browser_session, viz_e2e_base_url) -> None:
    browser_session.navigate(f"{viz_e2e_base_url.rstrip('/')}/")
    browser_session.wait_for("h1", timeout_seconds=60.0)
    assert TITLE in browser_session.get_text("h1")
