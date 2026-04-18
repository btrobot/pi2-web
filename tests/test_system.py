"""System-level contract tests for server entry and basic BS reachability."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

import main
from api.app import create_app


@pytest.fixture()
def app(mock_config):
    flask_app = create_app(mock_config)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_root_route_is_reachable(client) -> None:
    resp = client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.content_type


def test_bootstrap_route_is_reachable(client) -> None:
    resp = client.get("/api/bootstrap")

    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"app", "constraints", "modes", "i18n"}


def test_main_defaults_to_server_mode(mock_config) -> None:
    with (
        patch("main._load_config", return_value=mock_config),
        patch("api.app.run_server") as run_server,
        patch("app.cli.run_cli") as run_cli,
        patch.object(sys, "argv", ["main.py"]),
    ):
        main.main()

    run_server.assert_called_once_with(mock_config)
    run_cli.assert_not_called()


def test_main_cli_flag_uses_debug_cli_path(mock_config) -> None:
    with (
        patch("main._load_config", return_value=mock_config),
        patch("api.app.run_server") as run_server,
        patch("app.cli.run_cli") as run_cli,
        patch.object(sys, "argv", ["main.py", "--cli"]),
    ):
        main.main()

    run_cli.assert_called_once_with(mock_config)
    run_server.assert_not_called()


def test_main_server_flag_remains_explicitly_supported(mock_config) -> None:
    with (
        patch("main._load_config", return_value=mock_config),
        patch("api.app.run_server") as run_server,
        patch("app.cli.run_cli") as run_cli,
        patch.object(sys, "argv", ["main.py", "--server"]),
    ):
        main.main()

    run_server.assert_called_once_with(mock_config)
    run_cli.assert_not_called()
