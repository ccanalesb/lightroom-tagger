import os
from dotenv import load_dotenv

load_dotenv()

FLASK_HOST = os.getenv('FLASK_HOST', 'localhost')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
DATABASE_PATH = os.getenv('DATABASE_PATH', '../visualizer.db')
LIBRARY_DB = os.getenv('LIBRARY_DB', '../../library.db')
INSTAGRAM_DIR = os.getenv('INSTAGRAM_DIR', '/tmp/instagram_images')
THUMBNAIL_DIR = os.getenv('THUMBNAIL_DIR', '../thumbnails')