from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db  # Updated import

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))  # Keep for compatibility
    is_admin = db.Column(db.Boolean, default=False)  # New field

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    description = db.Column(db.Text)
    questions = db.relationship('Question', backref='test', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    type = db.Column(db.String(50))  # e.g., 'multiple_choice', 'true_false', 'flashcard'
    text = db.Column(db.Text)
    options = db.Column(db.Text)  # JSON string
    correct = db.Column(db.String(255))
    explanation = db.Column(db.Text)
    image = db.Column(db.String(255))  # Upload path

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    mode = db.Column(db.String(20))
    score = db.Column(db.Integer)
    answers = db.Column(db.Text)  # JSON
    date = db.Column(db.DateTime, default=datetime.utcnow)  # New field