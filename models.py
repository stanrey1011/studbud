from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db  # Updated to non-circular import

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))  # Keep for compatibility
    is_admin = db.Column(db.Boolean, default=False)  # For quick role checks

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    time_limit = db.Column(db.Integer)
    num_questions = db.Column(db.Integer)
    questions = db.relationship('Question', backref='test', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    type = db.Column(db.String(50))  # e.g., 'multiple_choice', 'true_false', 'flashcard'
    text = db.Column(db.Text)
    options = db.Column(db.Text)  # JSON string for options
    correct = db.Column(db.String(255))
    explanation = db.Column(db.Text)
    image = db.Column(db.String(255))  # Path to uploaded screenshot

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    mode = db.Column(db.String(20))
    score = db.Column(db.Integer)
    answers = db.Column(db.Text)  # JSON of user answers
    date = db.Column(db.DateTime, default=datetime.utcnow)  # For sorting history
    test = db.relationship('Test', backref='histories', lazy=True)  # Add this line