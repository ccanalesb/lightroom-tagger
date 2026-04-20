import socket

import pytest

from app import _refuse_if_port_in_use, create_app


def test_create_app_returns_flask_app():
    app = create_app()
    assert app is not None
    assert app.name == 'backend'

def test_app_has_required_endpoints():
    app = create_app()
    client = app.test_client()

    response = client.get('/api/status')
    assert response.status_code == 200

    catalog_status = client.get('/api/catalog/status')
    assert catalog_status.status_code == 200
    payload = catalog_status.get_json()
    assert 'cached' in payload
    assert isinstance(payload['cached'], bool)


def test_refuse_if_port_in_use_exits_when_port_bound(monkeypatch):
    monkeypatch.delenv('WERKZEUG_RUN_MAIN', raising=False)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        _host, port = listener.getsockname()
        with pytest.raises(SystemExit) as excinfo:
            _refuse_if_port_in_use('127.0.0.1', port)
        assert excinfo.value.code == 1


def test_refuse_if_port_in_use_returns_when_port_free(monkeypatch):
    monkeypatch.delenv('WERKZEUG_RUN_MAIN', raising=False)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as finder:
        finder.bind(('127.0.0.1', 0))
        _host, free_port = finder.getsockname()
    _refuse_if_port_in_use('127.0.0.1', free_port)


def test_refuse_if_port_in_use_skips_in_reloader_child(monkeypatch):
    monkeypatch.setenv('WERKZEUG_RUN_MAIN', 'true')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        _host, port = listener.getsockname()
        _refuse_if_port_in_use('127.0.0.1', port)
