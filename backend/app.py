from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import config
import os
from database import init_db

db = None
socketio = None

def create_app():
    global db, socketio
    app = Flask(__name__)
    app.name = 'backend'
    
    CORS(app, origins=[config.FRONTEND_URL])
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    db_path = os.path.join(os.path.dirname(__file__), config.DATABASE_PATH)
    db = init_db(db_path)
    app.db = db
    
    from api import jobs, images, system
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/images')
    app.register_blueprint(system.bp, url_prefix='/api')
    
    from websocket.events import register_socket_events
    register_socket_events(socketio)
    
    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, allow_unsafe_werkzeug=True)