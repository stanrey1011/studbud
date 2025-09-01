from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from models import User, Test, Question, History
from forms import UserForm, TestForm, QuestionForm, ImportForm
from extensions import db
import os
import json
from io import BytesIO
import sqlite3

admin_bp = Blueprint('admin', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def normalize_image_path(image_path):
    if image_path and image_path.startswith('uploads/'):
        return os.path.basename(image_path)  # Remove 'uploads/' prefix, keep only filename
    return image_path

@admin_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied: Admin only.', 'danger')
        return redirect(url_for('user.dashboard'))
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
                    conn = sqlite3.connect(current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
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
                    image_path = normalize_image_path(q.get('image'))  # Normalize imported image paths
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

@admin_bp.route('/export_tests')
@login_required
def export_tests():
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
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

@admin_bp.route('/create_test', methods=['GET', 'POST'])
@login_required
def create_test():
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
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
        return redirect(url_for('admin.edit_test', test_id=test.id))
    return render_template('admin/edit_test.html', form=form, q_form=QuestionForm(), questions=[], test=None)

@admin_bp.route('/edit_test/<int:test_id>', methods=['GET', 'POST'])
@login_required
def edit_test(test_id):
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
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
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
            image_path = filename  # Store only filename
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

@admin_bp.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    question = Question.query.get_or_404(question_id)
    db.session.refresh(question)
    # Normalize image path and persist to database on load
    normalized_image = normalize_image_path(question.image)
    if normalized_image != question.image:
        question.image = normalized_image
        db.session.commit()
    form = QuestionForm(obj=question)
    try:
        form.parsed_options = json.loads(form.options.data) if form.options.data else []
        form.correct.choices = [(opt, opt) for opt in form.parsed_options] if form.parsed_options else []
    except json.JSONDecodeError:
        form.parsed_options = []
        form.correct.choices = []
    submitted_correct = form.correct.data if request.method == 'POST' else None
    if request.method == 'GET':
        if question.type == 'mrq' and question.correct:
            form.correct.data = question.correct.split(', ') if question.correct else []
        elif question.type in ['mcq', 'tf']:
            form.correct.data = question.correct
    if request.method == 'POST':
        if not form.validate_on_submit():
            flash(f'Validation failed. Form data: {form.data}, Errors: {form.errors}', 'danger')
            file = request.files.get('image')
            image_path = question.image
            if request.form.get('delete_image') == 'y' and question.image:
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image)
                if os.path.exists(full_path):
                    os.remove(full_path)
                image_path = None
            if file and isinstance(file, FileStorage) and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                file.save(full_path)
                image_path = filename  # Store only filename
            correct = request.form.get('correct') if question.type in ['mcq', 'tf'] else request.form.getlist('correct')
            if not correct:
                flash('No correct answer selected.', 'warning')
            if question.type == 'mrq':
                if isinstance(correct, list):
                    correct = ', '.join(correct)
                elif isinstance(correct, str):
                    correct = correct
                else:
                    correct = ''
            elif question.type in ['mcq', 'tf']:
                correct = correct
            question.type = request.form.get('type')
            question.text = request.form.get('text')
            question.options = request.form.get('options') if request.form.get('options') else '[]'
            question.correct = correct
            question.explanation = request.form.get('explanation')
            question.image = image_path
            try:
                db.session.commit()
                flash(f'Question updated successfully (bypassed validation). Saved correct: {correct}', 'success')
                db.session.refresh(question)
                form = QuestionForm(obj=question)
                try:
                    form.parsed_options = json.loads(form.options.data) if form.options.data else []
                    form.correct.choices = [(opt, opt) for opt in form.parsed_options] if form.parsed_options else []
                except json.JSONDecodeError:
                    form.parsed_options = []
                    form.correct.choices = []
                if question.type == 'mrq' and question.correct:
                    form.correct.data = question.correct.split(', ') if question.correct else []
                elif question.type in ['mcq', 'tf']:
                    form.correct.data = question.correct
                return render_template('admin/edit_question.html', form=form, question=question)
            except Exception as e:
                flash(f'Error saving question: {str(e)}', 'danger')
        else:
            file = form.image.data
            image_path = question.image
            if form.delete_image.data and question.image:
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image)
                if os.path.exists(full_path):
                    os.remove(full_path)
                image_path = None
            if file and isinstance(file, FileStorage) and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                file.save(full_path)
                image_path = filename  # Store only filename
            correct = request.form.get('correct') if question.type in ['mcq', 'tf'] else request.form.getlist('correct')
            if not correct:
                flash('No correct answer selected.', 'warning')
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
                db.session.refresh(question)
                form = QuestionForm(obj=question)
                try:
                    form.parsed_options = json.loads(form.options.data) if form.options.data else []
                    form.correct.choices = [(opt, opt) for opt in form.parsed_options] if form.parsed_options else []
                except json.JSONDecodeError:
                    form.parsed_options = []
                    form.correct.choices = []
                if question.type == 'mrq' and question.correct:
                    form.correct.data = question.correct.split(', ') if question.correct else []
                elif question.type in ['mcq', 'tf']:
                    form.correct.data = question.correct
                return render_template('admin/edit_question.html', form=form, question=question)
            except Exception as e:
                flash(f'Error saving question: {str(e)}', 'danger')
    elif request.method == 'GET':
        if question.type == 'mrq' and question.correct:
            form.correct.data = question.correct.split(', ') if question.correct else []
        elif question.type in ['mcq', 'tf']:
            form.correct.data = question.correct
    return render_template('admin/edit_question.html', form=form, question=question)

@admin_bp.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    question = Question.query.get_or_404(question_id)
    test_id = question.test_id
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted successfully.', 'success')
    return redirect(url_for('admin.edit_test', test_id=test_id))

@admin_bp.route('/delete_test/<int:test_id>', methods=['POST'])
@login_required
def delete_test(test_id):
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    test = Test.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()
    if not Test.query.first():
        try:
            conn = sqlite3.connect(current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
            if cursor.fetchone():
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('test', 'question')")
                conn.commit()
            conn.close()
        except sqlite3.OperationalError as e:
            flash(f'Warning: Could not reset sequence: {str(e)}', 'warning')
    flash('Test deleted successfully.', 'success')
    return redirect(url_for('admin.edit_test', test_id=test_id))