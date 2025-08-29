# StudBud: Lightweight Self-Hosted IT Cert Study App

A versatile, lightweight web-based study tool for IT certification prep (e.g., Cisco CCNA). Features include multiple-choice questions (MCQ), true/false (T/F), flashcards; study mode with immediate answer reveals and explanations; test simulation mode with timing and scoring; history tracking for past sessions; image uploads for network topologies/screenshots; admin console for creating/editing tests and users; user console for taking tests. Built with Python/Flask for simplicity and flexibility, using SQLite as the database (file-based, no server required). Deploy as a Docker application for easy self-hosting.

## Quick Start (Local Setup for Testing/Dev)

1. Clone the repo and enter the directory:
   git clone https://github.com/stanrey1011/studbud.git
   cd studbud

2. Set up virtual environment and install dependencies:
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt

3. Initialize the database and create the initial admin user:
   flask db init  # Only needed once
   flask db migrate
   flask db upgrade
   flask shell
   
   In the shell (enter one line at a time):
   from models import db, User
   u = User(username='admin', role='admin')
   u.set_password('dojo')  # Change this password in production
   db.session.add(u)
   db.session.commit()
   exit()

4. Run the app:
   python app.py
   
   - Access http://localhost:5000/login in your browser.
   - Log in as admin/dojo.
   - Use admin console to create tests/questions (with topology uploads), import JSON dumps, manage users.
   - Log in as a user to take tests in study/test modes and view history.

## JSON Import Format (For Test Dumps)
Upload a .json file in the admin dashboard with this structure (adapt from PDF dumps):
[
  {
    "test_name": "Cisco CCNA Basics",
    "description": "Networking Fundamentals",
    "questions": [
      {
        "type": "mcq",
        "text": "What is the purpose of the OSI model?",
        "options": ["To standardize networking", "To encrypt data", "To route packets", "To switch frames"],
        "correct": "To standardize networking",
        "explanation": "The OSI model provides a framework for networking standards.",
        "image": null  // Optional path to pre-uploaded topology
      },
      {
        "type": "tf",
        "text": "IP addresses are 32 bits in IPv4.",
        "options": ["True", "False"],
        "correct": "True",
        "explanation": "Yes, IPv4 uses 32-bit addresses."
      },
      {
        "type": "flashcard",
        "text": "What does TCP stand for?",
        "options": {"back": "Transmission Control Protocol"},
        "correct": "Transmission Control Protocol",
        "explanation": ""
      }
    ]
  }
]

## Docker Deployment (For Production Self-Hosting)
1. Clone the repo (as above).

2. Build the Docker image:
   docker build -t studbud .

3. Run the container:
   docker run -p 5000:5000 -v $(pwd)/studbud.db:/app/studbud.db -v $(pwd)/uploads:/app/uploads studbud
   
   - On first run, initialize DB and admin user inside the container:
     docker exec -it <container_id> flask db upgrade
     docker exec -it <container_id> flask shell
     
     (Use the same shell commands as local step 3 to create admin.)

4. Access http://localhost:5000/login. Volumes persist DB and uploads.

## Troubleshooting
- Missing folders: mkdir uploads (for topology images; gitignored).
- Errors: Check terminal logs (debug mode enabled). Update .env for secrets (gitignore it).
- Expand: Add features in app.py (e.g., question delete/edit), quiz.js (advanced modes).

For contributions or issues, open a PR/issue on GitHub.