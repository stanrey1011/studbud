from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON  # For portable JSON support
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import UserMixin  # Add this import

db = SQLAlchemy()

class User(db.Model, UserMixin):  # Add UserMixin here
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    questions = db.relationship('Question', backref='test', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'mcq', 'tf', 'flashcard'
    text = db.Column(db.Text, nullable=False)
    options = db.Column(JSON)  # JSON for options array/dict
    correct = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)
    image = db.Column(db.String(200))  # Path to uploaded topology

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    mode = db.Column(db.String(50), nullable=False)  # 'study', 'test'
    score = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    answers = db.Column(JSON)  # JSON for answers log