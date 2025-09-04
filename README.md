# StudBud - IT Certification Study Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, self-hosted web application for IT certification study and practice testing. Built with Python/Flask and SQLite, StudBud offers flexible study modes for certifications like Cisco CCNA, CCNP, and more.

## ✨ Features

- **Multiple Question Types**: MCQ, True/False, Multiple Response, Match Questions, and Flashcards
- **Study Modes**:
  - **Study Mode**: Immediate feedback with explanations
  - **Simulation Mode**: Timed exam practice
  - **Flashcard Mode**: Quick review and memorization
- **Image Support**: Upload network topology diagrams and screenshots
- **Progress Tracking**: Test history and score analytics
- **Admin Console**: Create/edit tests, manage users, import/export data
- **JSON Import/Export**: Bulk test data management
- **Docker Support**: Easy deployment with Docker Compose

## 🚀 Quick Start

### Option 1: Docker (Recommended)

1. **Clone and start**:
   ```bash
   git clone https://github.com/yourusername/studbud.git
   cd studbud
   docker-compose up -d
   ```

2. **Access the app**: Open http://localhost:3000
3. **Default login**: `admin` / `dojo`

### Option 2: Local Development

1. **Setup environment**:
   ```bash
   git clone https://github.com/yourusername/studbud.git
   cd studbud
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

2. **Initialize database**:
   ```bash
   flask db upgrade
   python app.py
   ```

3. **Create admin user**:
   ```bash
   flask shell
   # In shell:
   from models import db, User
   u = User(username='admin', role='admin', is_admin=True)
   u.set_password('dojo')
   db.session.add(u)
   db.session.commit()
   exit()
   ```

## 📋 Usage

### For Students
1. **Login** with your credentials
2. **Select a test** from the dashboard  
3. **Choose study mode**:
   - **Study**: Learn with immediate feedback
   - **Flashcard**: Quick review mode
   - **Simulation**: Timed exam practice
4. **Track progress** in Test History

### For Admins
1. **Manage Tests**: Create, edit, and organize certification tests
2. **Import Data**: Bulk import questions via JSON files
3. **User Management**: Create student accounts
4. **Analytics**: View test performance and usage statistics

## 📄 JSON Import Format

```json
[{
  "test_name": "CCNA Practice Test",
  "description": "Cisco CCNA certification practice questions",
  "questions": [{
    "type": "mcq",
    "text": "What is the default administrative distance for OSPF?",
    "options": ["A. 90", "B. 100", "C. 110", "D. 120"],
    "correct": "C",
    "explanation": "OSPF has an administrative distance of 110.",
    "image": "ospf-topology.png"
  }]
}]
```

## 🐳 Docker Deployment

See [README-docker.md](README-docker.md) for detailed Docker deployment instructions including:
- Production setup
- Environment variables
- Volume management
- Health monitoring
- Backup procedures

## 🔧 Development

### Project Structure
```
├── app.py              # Main Flask application
├── models.py           # Database models
├── forms.py            # WTForms definitions
├── admin.py            # Admin routes and logic
├── user.py             # Student interface
├── templates/          # Jinja2 templates
├── static/             # CSS, JS, uploads
├── tests/              # Sample JSON test data
└── migrations/         # Database migrations
```

### Adding New Features
1. **Models**: Update `models.py` for database changes
2. **Forms**: Add new forms in `forms.py`
3. **Routes**: Implement in `admin.py` or `user.py`
4. **Templates**: Create/update HTML templates
5. **Migrations**: Run `flask db migrate` for schema changes

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for IT certification enthusiasts
- Inspired by the need for lightweight, self-hosted study tools
- Community-driven development approach

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/yourusername/studbud/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/yourusername/studbud/discussions)
- 📖 **Documentation**: Check the `templates/admin/instructions.html` for detailed usage guide

---

Made with ❤️ for the IT community