from app import create_app


def test_create_app_returns_flask_app():
    app = create_app()
    assert app is not None
    assert app.name == 'backend'

def test_app_has_required_endpoints():
    app = create_app()
    client = app.test_client()

    response = client.get('/api/status')
    assert response.status_code == 200
