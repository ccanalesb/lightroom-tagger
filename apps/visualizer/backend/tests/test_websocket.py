import pytest
import tempfile
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from database import init_db

@pytest.fixture
def socketio_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        
        app = Flask(__name__)
        app.name = 'backend'
        CORS(app, origins=["*"])
        
        app.db = init_db(db_path)
        
        from api import jobs, images, system
        app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
        app.register_blueprint(images.bp, url_prefix='/api/instagram-images')
        app.register_blueprint(system.bp, url_prefix='/api')
        
        socketio = SocketIO(app, cors_allowed_origins="*")
        
        from websocket.events import register_socket_events
        register_socket_events(socketio)
        
        client = socketio.test_client(app)
        yield client

def test_socket_connect(socketio_client):
    assert socketio_client.is_connected()

def test_socket_subscribe_to_job(socketio_client):
    socketio_client.emit('subscribe_job', {'job_id': 'test-job-id'})
    
    received = socketio_client.get_received()
    assert len(received) > 0
    assert any(r['name'] == 'subscribed' for r in received)

def test_socket_emit_job_update(socketio_client):
    socketio_client.emit('subscribe_job', {'job_id': 'test-job-id'})
    
    received = socketio_client.get_received()
    assert any(r['name'] == 'subscribed' for r in received)