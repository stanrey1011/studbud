import os
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from extensions import db
from auth import auth_bp
from admin import admin_bp
from user import user_bp
from utils import allowed_file, calculate_score

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Register Blueprints with configuration
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin', config=app.config)
app.register_blueprint(user_bp, url_prefix='/user')

# Import models at the end to avoid circular imports
from models import User, Test, Question, History

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=3000)