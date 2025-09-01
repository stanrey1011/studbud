import os
from flask import Flask, send_from_directory
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from extensions import db
from auth import auth_bp
from admin import admin_bp
from user import user_bp
from utils import allowed_file
import json

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return db.session.get(User, int(user_id))

# Register from_json filter
@app.template_filter('from_json')
def from_json(value):
    return json.loads(value) if value else {}

# Serve uploaded images
@app.route('/uploads/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(user_bp, url_prefix='/user')

# Import models at the end to avoid circular imports
from models import User, Test, Question, History

# Create upload folder
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)