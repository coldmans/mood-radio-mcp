from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "preflight_endpoint.py"
spec = importlib.util.spec_from_file_location("preflight_endpoint", MODULE_PATH)
assert spec is not None
preflight_endpoint = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(preflight_endpoint)


def test_derive_urls_from_base_url() -> None:
    metadata, health, mcp = preflight_endpoint.derive_urls("https://example.com")

    assert metadata == "https://example.com/"
    assert health == "https://example.com/health"
    assert mcp == "https://example.com/mcp"


def test_derive_urls_from_mcp_url() -> None:
    metadata, health, mcp = preflight_endpoint.derive_urls("https://example.com/mcp")

    assert metadata == "https://example.com/"
    assert health == "https://example.com/health"
    assert mcp == "https://example.com/mcp"


def test_derive_urls_from_health_url() -> None:
    metadata, health, mcp = preflight_endpoint.derive_urls("https://example.com/health")

    assert metadata == "https://example.com/"
    assert health == "https://example.com/health"
    assert mcp == "https://example.com/mcp"


def test_derive_urls_rejects_relative_url() -> None:
    try:
        preflight_endpoint.derive_urls("example.com/mcp")
    except ValueError as exc:
        assert "absolute" in str(exc)
    else:
        raise AssertionError("relative URL should be rejected")
