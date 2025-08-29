from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Test, Question, History
from forms import LoginForm, UserForm, TestForm, QuestionForm, ImportForm
import os
import json

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in!')
            return redirect(url_for('admin_dashboard') if user.role == 'admin' else url_for('user_dashboard'))
        flash('Invalid credentials.')
    return render_template('admin/login.html', form=form)  # Place in templates/admin for organization

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))
    tests = Test.query.all()
    user_form = UserForm()
    import_form = ImportForm()
    if user_form.validate_on_submit():
        user = User(username=user_form.username.data, role=user_form.role.data)
        user.set_password(user_form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('User created.')
    if import_form.validate_on_submit():
        file = import_form.json_file.data
        if file:
            data = json.load(file)
            for test_data in data:
                test = Test(name=test_data['test_name'], description=test_data.get('description'))
                db.session.add(test)
                db.session.commit()
                for q in test_data.get('questions', []):
                    options = q.get('options')
                    question = Question(test_id=test.id, type=q['type'], text=q['text'],
                                        options=options, correct=q['correct'],
                                        explanation=q.get('explanation'), image=q.get('image'))
                    db.session.add(question)
            db.session.commit()
            flash('Imported from JSON.')
    return render_template('admin/dashboard.html', tests=tests, user_form=user_form, import_form=import_form)

@app.route('/admin/create_test', methods=['GET', 'POST'])
@login_required
def create_test():
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))
    form = TestForm()
    if form.validate_on_submit():
        test = Test(name=form.name.data, description=form.description.data)
        db.session.add(test)
        db.session.commit()
        flash('Test created.')
        return redirect(url_for('edit_test', test_id=test.id))
    return render_template('admin/edit_test.html', form=form, q_form=QuestionForm(), questions=[], test=Test(name='New Test'))

@app.route('/admin/edit_test/<int:test_id>', methods=['GET', 'POST'])
@login_required
def edit_test(test_id):
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))
    test = Test.query.get_or_404(test_id)
    form = TestForm(obj=test)
    q_form = QuestionForm()
    if form.validate_on_submit():
        test.name = form.name.data
        test.description = form.description.data
        db.session.commit()
        flash('Test updated.')
    if q_form.validate_on_submit():
        file = q_form.image.data
        image_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = filename
        options = json.loads(q_form.options.data) if q_form.options.data else None
        question = Question(test_id=test.id, type=q_form.type.data, text=q_form.text.data,
                            options=options, correct=q_form.correct.data,
                            explanation=q_form.explanation.data, image=image_path)
        db.session.add(question)
        db.session.commit()
        flash('Question added.')
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
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    if request.method == 'POST':
        data = request.json
        history = History(user_id=current_user.id, test_id=test_id, mode=mode, score=data.get('score', 0), answers=data.get('answers'))
        db.session.add(history)
        db.session.commit()
        return {'status': 'saved'}
    return render_template('user/quiz.html', test=test, questions=questions, mode=mode)

@app.route('/user/history')
@login_required
def history():
    histories = History.query.filter_by(user_id=current_user.id).order_by(History.date.desc()).all()
    return render_template('user/history.html', histories=histories)

@app.route('/admin/delete_test/<int:test_id>', methods=['POST'])
@login_required
def delete_test(test_id):
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))
    test = Test.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()
    flash('Test deleted.')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)