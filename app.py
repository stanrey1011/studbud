from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from config import Config
from extensions import db
from models import User, Test, Question, History
from forms import LoginForm, UserForm, TestForm, QuestionForm, ImportForm, SimStartForm
import os
import json
from io import BytesIO
from datetime import datetime
import time
import random
import sqlite3

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
    if hasattr(Test, 'num_questions'):
        tests = Test.query.all()
    else:
        tests = Test.query.options(db.load_only('id', 'name', 'description', 'time_limit')).all()
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
            if import_form.overwrite.data:
                Test.query.delete()
                Question.query.delete()
                db.session.commit()
                try:
                    conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
                    if cursor.fetchone():
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('test', 'question')")
                        conn.commit()
                    conn.close()
                except sqlite3.OperationalError as e:
                    flash(f'Warning: Could not reset sequence: {str(e)}', 'warning')
            for test_data in data:
                test_args = {
                    'name': test_data['test_name'],
                    'description': test_data.get('description', '')
                }
                if hasattr(Test, 'num_questions'):
                    test_args['num_questions'] = len(test_data.get('questions', []))
                test = Test(**test_args)
                db.session.add(test)
                db.session.commit()
                for q in test_data.get('questions', []):
                    image_path = os.path.basename(q.get('image')) if q.get('image') else None
                    question = Question(
                        test_id=test.id,
                        type=q['type'],
                        text=q['text'],
                        options=json.dumps(q.get('options', [])),
                        correct=q['correct'],
                        explanation=q.get('explanation', ''),
                        image=image_path
                    )
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
        questions = [
            {
                'id': q.id,
                'type': q.type,
                'text': q.text,
                'options': json.loads(q.options or '[]'),
                'correct': q.correct,
                'explanation': q.explanation,
                'image': q.image
            } for q in test.questions
        ]
        data.append({
            'test_name': test.name,
            'description': test.description,
            'questions': questions
        })
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
        test_args = {
            'name': form.name.data,
            'description': form.description.data,
            'time_limit': form.time_limit.data
        }
        if hasattr(Test, 'num_questions'):
            test_args['num_questions'] = form.num_questions.data
        test = Test(**test_args)
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
        test.time_limit = form.time_limit.data
        if hasattr(Test, 'num_questions'):
            test.num_questions = form.num_questions.data
        db.session.commit()
        flash('Test updated successfully.', 'success')
    if q_form.validate_on_submit():
        file = q_form.image.data
        image_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(full_path)
            image_path = filename
        correct = q_form.correct.data
        if q_form.type.data == 'mrq' and isinstance(q_form.correct.data, list):
            correct = ', '.join(q_form.correct.data)
        question = Question(
            test_id=test.id,
            type=q_form.type.data,
            text=q_form.text.data,
            options=q_form.options.data if q_form.options.data else '[]',
            correct=correct,
            explanation=q_form.explanation.data,
            image=image_path
        )
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully.', 'success')
    questions = Question.query.filter_by(test_id=test_id).all()
    return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=questions)

@app.route('/admin/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    question = Question.query.get_or_404(question_id)
    form = QuestionForm(obj=question)
    # Parse options for the template
    try:
        form.parsed_options = json.loads(form.options.data) if form.options.data else []
    except json.JSONDecodeError:
        form.parsed_options = []
    # Populate correct data based on question type
    if request.method == 'GET':
        if question.type == 'mrq' and question.correct:
            form.correct.data = question.correct.split(', ') if question.correct else []
        elif question.type in ['mcq', 'tf']:
            form.correct.data = question.correct
    if form.validate_on_submit():
        file = form.image.data
        image_path = question.image
        if form.delete_image.data and question.image:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], question.image)
            if os.path.exists(full_path):
                os.remove(full_path)
            image_path = None
        if file and isinstance(file, FileStorage) and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(full_path)
            image_path = filename
        correct = request.form.get('correct') if question.type in ['mcq', 'tf'] else request.form.getlist('correct')
        if question.type == 'mrq':
            if isinstance(correct, list):
                correct = ', '.join(correct)
            elif isinstance(correct, str):
                correct = correct
            else:
                correct = ''
        elif question.type in ['mcq', 'tf']:
            correct = correct
        question.type = form.type.data
        question.text = form.text.data
        question.options = form.options.data if form.options.data else '[]'
        question.correct = correct
        question.explanation = form.explanation.data
        question.image = image_path
        try:
            db.session.commit()
            flash(f'Question updated successfully. Saved correct: {correct}', 'success')
            # Re-populate form with saved data
            form = QuestionForm(obj=question)
            try:
                form.parsed_options = json.loads(form.options.data) if form.options.data else []
            except json.JSONDecodeError:
                form.parsed_options = []
            if question.type == 'mrq' and question.correct:
                form.correct.data = question.correct.split(', ') if question.correct else []
            elif question.type in ['mcq', 'tf']:
                form.correct.data = question.correct
            return render_template('admin/edit_question.html', form=form, question=question)
        except Exception as e:
            flash(f'Error saving question: {str(e)}', 'danger')
    elif request.method == 'GET':
        flash('Loading edit form for question.', 'info')  # Debug
    return render_template('admin/edit_question.html', form=form, question=question)

@app.route('/admin/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    question = Question.query.get_or_404(question_id)
    test_id = question.test_id
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted successfully.', 'success')
    return redirect(url_for('edit_test', test_id=test_id))

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    tests = Test.query.all()
    sim_form = SimStartForm()
    return render_template('user/dashboard.html', tests=tests, sim_form=sim_form)

def calculate_score(questions, user_answers):
    score = 0
    for question in questions:
        user_ans = user_answers.get(str(question.id))
        if question.type == 'mrq':
            correct = question.correct.split(', ') if question.correct else []
            user_ans = user_ans if isinstance(user_ans, list) else []
            if sorted(correct) == sorted(user_ans):
                score += 1
        elif question.type == 'tf':
            if str(user_ans).lower() == str(question.correct).lower():
                score += 1
        else:
            if user_ans == question.correct:
                score += 1
    return score

@app.route('/user/quiz/<int:test_id>/<string:mode>', methods=['GET', 'POST'])
@login_required
def quiz(test_id, mode):
    if mode not in ['study', 'sim']:
        flash('Invalid mode.', 'danger')
        return redirect(url_for('user_dashboard'))
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    if hasattr(Test, 'num_questions') and test.num_questions and test.num_questions < len(questions):
        questions = random.sample(questions, test.num_questions)

    if mode == 'study':
        if request.method == 'POST':
            try:
                data = request.json
                history = History(
                    user_id=current_user.id,
                    test_id=test_id,
                    mode=mode,
                    score=data.get('score', 0),
                    answers=json.dumps(data.get('answers', {}))
                )
                db.session.add(history)
                db.session.commit()
                return jsonify({'status': 'saved'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 400
        for q in questions:
            q.parsed_options = json.loads(q.options) if q.options else []
        return render_template('user/study_mode.html', test=test, questions=questions, mode=mode)

    custom_time = None
    if request.method == 'POST' and 'custom_time' in request.form:
        form = SimStartForm()
        if form.validate_on_submit():
            custom_time = form.custom_time.data or 0
    if 'sim_progress' not in session or session['sim_progress'].get('test_id') != test_id:
        effective_time_limit = (custom_time * 60) if custom_time is not None else ((test.time_limit or 0) * 60)
        session['sim_progress'] = {
            'test_id': test_id,
            'current': 0,
            'answers': {},
            'start_time': time.time(),
            'time_limit': effective_time_limit
        }

    progress = session['sim_progress']
    time_limit = progress['time_limit']
    elapsed = time.time() - progress['start_time']
    remaining = max(0, time_limit - elapsed) if time_limit > 0 else None

    if time_limit > 0 and elapsed > time_limit:
        score = calculate_score(questions, progress['answers'])
        history = History(
            user_id=current_user.id,
            test_id=test_id,
            mode=mode,
            score=score,
            answers=json.dumps(progress['answers'])
        )
        db.session.add(history)
        db.session.commit()
        session.pop('sim_progress')
        flash('Time up! Test submitted.', 'info')
        return render_template('user/results.html', score=score, total=len(questions), elapsed=elapsed, test=test)

    if request.method == 'POST' and 'question_id' in request.form:
        q_id = request.form.get('question_id')
        if q_id:
            answer = request.form.getlist('correct') if request.form.get('question_type') == 'mrq' else request.form.get('correct')
            progress['answers'][q_id] = answer

        if 'next' in request.form and progress['current'] < len(questions) - 1:
            progress['current'] += 1
        elif 'prev' in request.form and progress['current'] > 0:
            progress['current'] -= 1
        elif 'submit' in request.form or (time_limit > 0 and elapsed > time_limit):
            score = calculate_score(questions, progress['answers'])
            history = History(
                user_id=current_user.id,
                test_id=test_id,
                mode=mode,
                score=score,
                answers=json.dumps(progress['answers'])
            )
            db.session.add(history)
            db.session.commit()
            session.pop('sim_progress')
            return render_template('user/results.html', score=score, total=len(questions), elapsed=elapsed, test=test)
        session['sim_progress'] = progress

    current_question = questions[progress['current']]
    options_list = json.loads(current_question.options) if current_question.options else []
    selected = progress['answers'].get(str(current_question.id), [])

    return render_template(
        'user/simulation_mode.html',
        test=test,
        question=current_question,
        options=options_list,
        current=progress['current'] + 1,
        total=len(questions),
        remaining=remaining,
        selected=selected
    )

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
    if not Test.query.first():
        try:
            conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
            if cursor.fetchone():
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('test', 'question')")
                conn.commit()
            conn.close()
        except sqlite3.OperationalError as e:
            flash(f'Warning: Could not reset sequence: {str(e)}', 'warning')
    flash('Test deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=3000)