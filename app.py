from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from extensions import db  # New non-circular import
from models import User, Test, Question, History
from forms import LoginForm, UserForm, TestForm, QuestionForm, ImportForm
import os
import json
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))  # SQLAlchemy 2.0 compat

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_instructions'))
        else:
            return redirect(url_for('user_instructions'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_instructions' if user.is_admin else 'user_instructions'))
        flash('Invalid username or password.', 'danger')
    return render_template('admin/login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/admin/instructions')
@login_required
def admin_instructions():
    if not current_user.is_admin:
        return redirect(url_for('user_instructions'))
    return render_template('admin/instructions.html')

@app.route('/user/instructions')
@login_required
def user_instructions():
    return render_template('user/instructions.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied: Admin only.', 'danger')
        return redirect(url_for('user_dashboard'))
    tests = Test.query.all()
    user_form = UserForm()
    import_form = ImportForm()
    if user_form.validate_on_submit():
        user = User(username=user_form.username.data, role=user_form.role.data)
        user.set_password(user_form.password.data)
        user.is_admin = (user_form.role.data == 'admin')
        db.session.add(user)
        db.session.commit()
        flash('User created successfully.', 'success')
    if import_form.validate_on_submit():
        try:
            file = import_form.json_file.data
            data = json.load(file)
            for test_data in data:
                test = Test(name=test_data['test_name'], description=test_data.get('description', ''))
                db.session.add(test)
                db.session.commit()
                for q in test_data.get('questions', []):
                    question = Question(test_id=test.id, type=q['type'], text=q['text'],
                                        options=json.dumps(q.get('options', [])), correct=q['correct'],
                                        explanation=q.get('explanation', ''), image=q.get('image'))
                    db.session.add(question)
            db.session.commit()
            flash('Tests imported from JSON.', 'success')
        except Exception as e:
            flash(f'Import error: {str(e)}', 'danger')
    return render_template('admin/dashboard.html', tests=tests, user_form=user_form, import_form=import_form)

@app.route('/admin/export_tests')
@login_required
def export_tests():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    tests = Test.query.all()
    data = []
    for test in tests:
        questions = [{'type': q.type, 'text': q.text, 'options': json.loads(q.options or '[]'),
                      'correct': q.correct, 'explanation': q.explanation, 'image': q.image} for q in test.questions]
        data.append({'name': test.name, 'description': test.description, 'questions': questions})
    output = BytesIO()
    output.write(json.dumps(data, indent=4).encode('utf-8'))
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='tests_export.json', mimetype='application/json')

@app.route('/admin/create_test', methods=['GET', 'POST'])
@login_required
def create_test():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    form = TestForm()
    if form.validate_on_submit():
        test = Test(name=form.name.data, description=form.description.data)
        db.session.add(test)
        db.session.commit()
        flash('Test created successfully.', 'success')
        return redirect(url_for('edit_test', test_id=test.id))
    return render_template('admin/edit_test.html', form=form, q_form=QuestionForm(), questions=[], test=None)

@app.route('/admin/edit_test/<int:test_id>', methods=['GET', 'POST'])
@login_required
def edit_test(test_id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    test = Test.query.get_or_404(test_id)
    form = TestForm(obj=test)
    q_form = QuestionForm()
    if form.validate_on_submit():
        test.name = form.name.data
        test.description = form.description.data
        db.session.commit()
        flash('Test updated successfully.', 'success')
    if q_form.validate_on_submit():
        file = q_form.image.data
        image_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = filename
        options = q_form.options.data if q_form.options.data else '[]'  # JSON string
        question = Question(test_id=test.id, type=q_form.type.data, text=q_form.text.data,
                            options=options, correct=q_form.correct.data,
                            explanation=q_form.explanation.data, image=image_path)
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully.', 'success')
    questions = Question.query.filter_by(test_id=test_id).all()
    return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=questions)

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    tests = Test.query.all()
    return render_template('user/dashboard.html', tests=tests)

@app.route('/user/quiz/<int:test_id>/<string:mode>', methods=['GET', 'POST'])
@login_required
def quiz(test_id, mode):
    if mode not in ['study', 'sim']:
        flash('Invalid mode.', 'danger')
        return redirect(url_for('user_dashboard'))
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    if request.method == 'POST':
        try:
            data = request.json
            history = History(user_id=current_user.id, test_id=test_id, mode=mode,
                              score=data.get('score', 0), answers=json.dumps(data.get('answers', {})))
            db.session.add(history)
            db.session.commit()
            return jsonify({'status': 'saved'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
    return render_template('user/quiz.html', test=test, questions=questions, mode=mode)

@app.route('/user/history')
@login_required
def history():
    histories = History.query.filter_by(user_id=current_user.id).order_by(History.date.desc()).all()
    return render_template('user/history.html', histories=histories)

@app.route('/admin/delete_test/<int:test_id>', methods=['POST'])
@login_required
def delete_test(test_id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    test = Test.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()
    flash('Test deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)