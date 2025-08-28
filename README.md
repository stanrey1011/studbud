# StudBud: Lightweight Self-Hosted IT Cert Study App

Flexible web tool for Cisco/IT cert prep: MCQ, T/F, flashcards; study (reveal answers) & test modes; history; topology uploads; admin/user consoles.

## Setup
- `python -m venv venv && source venv/bin/activate`
- `pip install -r requirements.txt`
- Set .env vars
- `flask db init` (for migrations), `flask db migrate`, `flask db upgrade`
- `python app.py`

## Docker Deployment
Use docker-compose.yml for app + PostgreSQL.

## JSON Import Example
[{"test_name": "CCNA", "questions": [{"type": "mcq", "text": "...", "options": [...], "correct": "..."}]}]