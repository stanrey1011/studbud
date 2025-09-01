from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

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
    type = db.Column(db.String(50), nullable=False)  # e.g., 'multiple_choice', 'true_false', 'flashcard', 'match'
    text = db.Column(db.Text)  # Question text or description
    options = db.Column(db.Text)  # JSON string for options
    # For multiple_choice: ["option1", "option2", ...]
    # For true_false: ["True", "False"]
    # For match: {"terms": [{"id": 1, "text": "KEK"}, ...], "definitions": [{"id": 1, "text": "Key Encryption Key"}, ...]}
    correct = db.Column(db.Text)  # JSON string for correct answer(s)
    # For multiple_choice: "option1"
    # For true_false: "True"
    # For match: {"1": "1", "2": "2"} (term_id: definition_id)
    explanation = db.Column(db.Text)  # Feedback for study mode
    image = db.Column(db.String(255))  # Path to topology screenshot (nullable)

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    mode = db.Column(db.String(20))  # e.g., 'study', 'test'
    score = db.Column(db.Float)  # Changed to Float for fractional scores (e.g., 0.75)
    answers = db.Column(db.Text)  # JSON of user answers
    # For multiple_choice: {"question_id": "answer"}
    # For match: {"term_id": "definition_id"}
    date = db.Column(db.DateTime, default=datetime.utcnow)
    test = db.relationship('Test', backref='histories', lazy=True)