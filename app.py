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

# Register get_full_answer filter
@app.template_filter('get_full_answer')
def get_full_answer(correct_letter, options_json):
    """Get the full answer text from the options JSON given the correct letter/prefix."""
    try:
        options = json.loads(options_json) if options_json else []
        if not isinstance(options, list):
            return correct_letter
        
        # For multiple correct answers (MRQ), handle comma-separated values
        if ', ' in str(correct_letter):
            correct_letters = [letter.strip() for letter in str(correct_letter).split(', ')]
            full_answers = []
            for letter in correct_letters:
                for option in options:
                    if option.startswith(f"{letter}."):
                        full_answers.append(option)
                        break
                else:
                    full_answers.append(letter)  # Fallback to letter if not found
            return ', '.join(full_answers)
        
        # For single correct answer
        for option in options:
            if option.startswith(f"{correct_letter}."):
                return option
        
        # If no match found, return the original letter
        return correct_letter
    except (json.JSONDecodeError, AttributeError, TypeError):
        return correct_letter

# Serve uploaded images
@app.route('/uploads/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(user_bp, url_prefix='/user')

# Health check endpoint for Docker
@app.route('/health')
def health():
    return {'status': 'healthy', 'service': 'StudBud'}, 200

# Import models at the end to avoid circular imports
from models import User, Test, Question, History

# Create upload folder and initialize admin user
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()
    
    # Create or update admin user from environment variable
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin')
    admin_user = User.query.filter_by(username='admin').first()
    
    if admin_user:
        # Update existing admin user password
        admin_user.set_password(admin_password)
        admin_user.is_admin = True
        admin_user.role = 'admin'
    else:
        # Create new admin user
        admin_user = User(
            username='admin',
            role='admin',
            is_admin=True
        )
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
    
    try:
        db.session.commit()
        print(f"✅ Admin user configured with password from environment")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error configuring admin user: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)