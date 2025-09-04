# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StudBud is a Flask-based web application for IT certification study and practice testing. It supports multiple question types (MCQ, True/False, Match, Flashcard) with both study and simulation modes. The application uses SQLite for data storage and includes admin/user role management.

## Development Commands

### Local Development Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Database setup
flask db init     # Only needed once for new projects
flask db migrate  # Create migration after model changes
flask db upgrade  # Apply migrations to database

# Run development server (port 3000, not 5000)
python app.py
```

### Database Operations
```bash
# Create admin user via Flask shell
flask shell
# In shell:
from models import db, User
u = User(username='admin', role='admin', is_admin=True)
u.set_password('dojo')
db.session.add(u)
db.session.commit()
exit()

# Reset database (careful - destroys all data)
rm studbud.db
flask db upgrade
```

### Testing
- Test JSON files are located in `tests/` directory
- No automated test framework is currently configured
- Manual testing via web interface

## Architecture Overview

### Application Structure
- **Flask Blueprints**: `auth.py` (authentication), `admin.py` (admin functions), `user.py` (student interface)
- **Database Models**: User, Test, Question, History (in `models.py`)
- **Forms**: WTForms-based forms in `forms.py`
- **Templates**: Jinja2 templates in `templates/` with separate admin/user folders
- **Static Files**: CSS/JS in `static/`, uploaded images in `static/uploads/`

### Key Components

#### Database Schema
- **User**: Username, password hash, admin flag
- **Test**: Name, description, time limit, question count
- **Question**: Type (mcq/tf/match/flashcard), text, options (JSON), correct answers (JSON), explanations, optional images
- **History**: User test results with answers, scores, timestamps

#### Question Types
- **MCQ**: Multiple choice with single correct answer
- **True/False**: Binary choice questions  
- **Match**: Terms matched to definitions (stored as JSON mappings)
- **Flashcard**: Simple question/answer pairs

#### User Roles
- **Admin**: Full CRUD access via `/admin/` routes - manage users, tests, questions, view analytics
- **User**: Student access via `/user/` routes - take tests in study/sim modes, view history

### File Structure
```
├── app.py              # Main Flask app with blueprints
├── models.py           # SQLAlchemy models
├── forms.py            # WTForms definitions
├── auth.py             # Authentication blueprint
├── admin.py            # Admin functionality blueprint  
├── user.py             # Student interface blueprint
├── utils.py            # Helper functions (scoring, file handling)
├── config.py           # Flask configuration
├── extensions.py       # Database initialization
├── migrations/         # Flask-Migrate database migrations
├── templates/          # Jinja2 templates
│   ├── base.html       # Base template
│   ├── admin/          # Admin interface templates
│   └── user/           # Student interface templates
├── static/             # CSS, JS, and uploaded files
│   ├── css/
│   ├── js/
│   └── uploads/        # User-uploaded images (gitignored)
└── tests/              # Sample JSON test data
```

## Development Guidelines

### Database Changes
- Always create migrations for model changes: `flask db migrate -m "description"`
- Apply migrations with `flask db upgrade`
- JSON fields (Question.options, Question.correct, History.answers) store structured data

### Image Handling
- Images uploaded to `static/uploads/` directory
- Automatic compression to 800x600 with 85% quality
- Image paths normalized to remove 'uploads/' prefix in database storage

### JSON Import Format
Tests can be imported via admin interface using JSON format:
```json
[{
  "test_name": "Test Name",
  "description": "Test Description", 
  "questions": [{
    "type": "mcq|tf|match|flashcard",
    "text": "Question text",
    "options": ["option1", "option2"] // or match object,
    "correct": "correct_answer", // or match mappings,
    "explanation": "Answer explanation",
    "image": "filename.png" // optional
  }]
}]
```

### Security Notes
- User passwords hashed with Werkzeug
- Admin role required for `/admin/` routes
- File uploads restricted by extension and compressed
- SQL injection prevented by SQLAlchemy ORM
- CSRF protection via Flask-WTF

## Docker Deployment

Basic Dockerfile exists but may be empty. For production deployment:
- Use `gunicorn` as WSGI server (included in requirements.txt)
- Mount `studbud.db` and `static/uploads/` as persistent volumes
- Set `SECRET_KEY` environment variable
- Consider using PostgreSQL for production instead of SQLite