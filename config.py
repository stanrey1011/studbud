import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'your-fallback-secret-key'  # Fallback for safety
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'studbud.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')  # Path for image uploads (e.g., network topologies)