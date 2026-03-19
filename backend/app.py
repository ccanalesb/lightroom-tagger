from flask import Flask
from flask_cors import CORS
import config

def create_app():
    app = Flask(__name__)
    app.name = 'backend'
    
    CORS(app, origins=[config.FRONTEND_URL])
    
    from api import jobs, images, system
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/instagram-images')
    app.register_blueprint(system.bp, url_prefix='/api')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)