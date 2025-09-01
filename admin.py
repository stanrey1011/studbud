from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from models import User, Test, Question, History
from forms import UserForm, TestForm, QuestionForm, ImportForm, PasswordForm
from extensions import db
from utils import allowed_file
import os
import json
from io import BytesIO
import sqlite3
from PIL import Image
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

def normalize_image_path(image_path):
    if image_path and image_path.startswith('uploads/'):
        return os.path.basename(image_path)
    return image_path

def compress_image(file_path):
    img = Image.open(file_path)
    img.thumbnail((800, 600))
    img.save(file_path, optimize=True, quality=85)

@admin_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied: Admin only.', 'danger')
        return redirect(url_for('user.dashboard'))
    user_form = UserForm()
    password_form = PasswordForm()
    users = User.query.all()
    if user_form.validate_on_submit():
        user = User(username=user_form.username.data, role=user_form.role.data)
        user.set_password(user_form.password.data)
        user.is_admin = (user_form.role.data == 'admin')
        db.session.add(user)
        try:
            db.session.commit()
            flash('User created successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
    return render_template('admin/create_user.html', user_form=user_form, password_form=password_form, users=users)

@admin_bp.route('/tests', methods=['GET', 'POST'])
@login_required
def tests():
    if not current_user.is_admin:
        flash('Access denied: Admin only.', 'danger')
        return redirect(url_for('user.dashboard'))
    if hasattr(Test, 'num_questions'):
        tests = Test.query.all()
    else:
        tests = Test.query.options(db.load_only('id', 'name', 'description', 'time_limit')).all()
    import_form = ImportForm()
    if import_form.validate_on_submit():
        try:
            file = import_form.json_file.data
            data = json.load(file)
            total_tests = len(data)
            total_questions = sum(len(test_data.get('questions', [])) for test_data in data)
            logger.debug(f'Importing {total_tests} tests with {total_questions} questions')
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
            imported_questions = 0
            for test_data in data:
                if not isinstance(test_data, dict) or 'test_name' not in test_data:
                    logger.warning(f'Skipping invalid test data: {test_data}')
                    continue
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
                    if not isinstance(q, dict) or 'type' not in q or 'text' not in q:
                        logger.warning(f'Skipping invalid question data: {q}')
                        continue
                    image_path = normalize_image_path(q.get('image'))
                    if q['type'] == 'match':
                        if not (q.get('terms') and q.get('definitions') and q.get('correct_mappings')):
                            logger.warning(f'Skipping match question due to missing terms/definitions/mappings: {q}')
                            continue
                        options = json.dumps({
                            'terms': q.get('terms', []),
                            'definitions': q.get('definitions', [])
                        })
                        correct = json.dumps(q.get('correct_mappings', {}))
                    else:
                        options = json.dumps(q.get('options', []))
                        correct = q.get('correct', '')
                    question = Question(
                        test_id=test.id,
                        type=q['type'],
                        text=q['text'],
                        options=options,
                        correct=correct,
                        explanation=q.get('explanation', ''),
                        image=image_path
                    )
                    db.session.add(question)
                    imported_questions += 1
                db.session.commit()
            logger.debug(f'Imported {imported_questions} questions out of {total_questions}')
            if imported_questions < total_questions:
                flash(f'Imported {imported_questions} out of {total_questions} questions. Check logs for skipped questions.', 'warning')
            else:
                flash('Tests imported from JSON.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Import error: {str(e)}', 'danger')
            logger.error(f'Import error: {str(e)}')
    return render_template('admin/dashboard.html', tests=tests, import_form=import_form)

@admin_bp.route('/edit_user/<int:user_id>', methods=['POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied: Admin only.', 'danger')
        return redirect(url_for('user.dashboard'))
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.dashboard'))
    form = PasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Password updated successfully.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {field}: {error}', 'danger')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied: Admin only.', 'danger')
        return redirect(url_for('user.dashboard'))
    if user_id == current_user.id:
        flash('Cannot delete your own account.', 'danger')
        return redirect(url_for('admin.dashboard'))
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.dashboard'))
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/export_tests')
@login_required
def export_tests():
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    tests = Test.query.all()
    data = []
    total_questions = 0
    for test in tests:
        questions = []
        for q in test.questions:
            question_data = {
                'id': q.id,
                'type': q.type,
                'text': q.text,
                'explanation': q.explanation,
                'image': q.image
            }
            try:
                if q.type == 'match':
                    options = json.loads(q.options or '{}')
                    question_data['terms'] = options.get('terms', [])
                    question_data['definitions'] = options.get('definitions', [])
                    question_data['correct_mappings'] = json.loads(q.correct or '{}')
                else:
                    question_data['options'] = json.loads(q.options or '[]')
                    question_data['correct'] = q.correct
                questions.append(question_data)
                total_questions += 1
            except json.JSONDecodeError as e:
                logger.warning(f'Skipping question ID {q.id} due to invalid JSON: {str(e)}')
                continue
        data.append({
            'test_name': test.name,
            'description': test.description,
            'questions': questions
        })
    logger.debug(f'Exported {len(tests)} tests with {total_questions} questions')
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
            compress_image(full_path)
            image_path = filename
        if q_form.type.data == 'match':
            try:
                terms = json.loads(q_form.options.data).get('terms', []) if q_form.options.data else []
                definitions = json.loads(q_form.options.data).get('definitions', []) if q_form.options.data else []
                correct_mappings = json.loads(q_form.correct.data) if q_form.correct.data else {}
                logger.debug(f'Adding question to test ID {test_id}: Terms {terms}, Definitions {definitions}, Mappings {correct_mappings}')
                if len(terms) > 8 or len(definitions) > 8:
                    flash('Maximum of 8 term-definition pairs allowed.', 'danger')
                    return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=test.questions)
                options = json.dumps({'terms': terms, 'definitions': definitions})
                correct = json.dumps(correct_mappings)
            except json.JSONDecodeError:
                flash('Invalid JSON format for terms, definitions, or mappings.', 'danger')
                return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=test.questions)
        else:
            options = q_form.options.data if q_form.options.data else '[]'
            correct = q_form.correct.data
            if q_form.type.data == 'mrq' and isinstance(q_form.correct.data, list):
                correct = ', '.join(q_form.correct.data)
        question = Question(
            test_id=test.id,
            type=q_form.type.data,
            text=q_form.text.data,
            options=options,
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
    normalized_image = normalize_image_path(question.image)
    if normalized_image != question.image:
        question.image = normalized_image
        db.session.commit()
    form = QuestionForm(obj=question)
    parsed_terms = []
    parsed_definitions = []
    parsed_mappings = {}
    parsed_options = []
    try:
        if question.type == 'match':
            options = json.loads(question.options or '{}')
            parsed_terms = options.get('terms', [])
            parsed_definitions = options.get('definitions', [])
            parsed_mappings = json.loads(question.correct or '{}')
            logger.debug(f'Loading question ID {question_id}: Terms {parsed_terms}, Definitions {parsed_definitions}, Mappings {parsed_mappings}')
        else:
            parsed_options = json.loads(question.options or '[]')
            form.correct.choices = [(opt, opt) for opt in parsed_options] if parsed_options else []
    except json.JSONDecodeError:
        parsed_options = []
        parsed_terms = []
        parsed_definitions = []
        parsed_mappings = {}
        form.correct.choices = []
        flash('Invalid JSON data in question options or correct answer.', 'warning')
    if request.method == 'GET':
        if question.type == 'mrq' and question.correct:
            form.correct.data = question.correct.split(', ') if question.correct else []
        elif question.type in ['mcq', 'tf']:
            form.correct.data = question.correct
        elif question.type == 'match':
            form.correct.data = json.dumps(parsed_mappings)
            form.options.data = json.dumps({'terms': parsed_terms, 'definitions': parsed_definitions})
    if form.validate_on_submit():
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
            compress_image(full_path)
            image_path = filename
        if form.type.data == 'match':
            try:
                terms = json.loads(form.options.data).get('terms', []) if form.options.data else []
                definitions = json.loads(form.options.data).get('definitions', []) if form.options.data else []
                correct_mappings = json.loads(form.correct.data) if form.correct.data else {}
                logger.debug(f'Saving question ID {question_id}: Terms {terms}, Definitions {definitions}, Mappings {correct_mappings}')
                if len(terms) > 8 or len(definitions) > 8:
                    flash('Maximum of 8 term-definition pairs allowed.', 'danger')
                    return render_template('admin/edit_question.html', form=form, question=question, parsed_terms=parsed_terms, parsed_definitions=parsed_definitions, parsed_mappings=parsed_mappings)
                options = json.dumps({'terms': terms, 'definitions': definitions})
                correct = json.dumps(correct_mappings)
            except json.JSONDecodeError:
                flash('Invalid JSON format for terms, definitions, or mappings.', 'danger')
                return render_template('admin/edit_question.html', form=form, question=question, parsed_terms=parsed_terms, parsed_definitions=parsed_definitions, parsed_mappings=parsed_mappings)
        else:
            options = form.options.data if form.options.data else '[]'
            correct = form.correct.data
            if form.type.data == 'mrq' and isinstance(form.correct.data, list):
                correct = ', '.join(form.correct.data)
        question.type = form.type.data
        question.text = form.text.data
        question.options = options
        question.correct = correct
        question.explanation = form.explanation.data
        question.image = image_path
        db.session.commit()
        flash('Question updated successfully.', 'success')
        return redirect(url_for('admin.edit_test', test_id=question.test_id))
    return render_template('admin/edit_question.html', form=form, question=question, parsed_terms=parsed_terms, parsed_definitions=parsed_definitions, parsed_mappings=parsed_mappings)

@admin_bp.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    question = Question.query.get_or_404(question_id)
    test_id = question.test_id
    if question.image:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image)
        if os.path.exists(full_path):
            os.remove(full_path)
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
    for question in test.questions:
        if question.image:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image)
            if os.path.exists(full_path):
                os.remove(full_path)
    db.session.delete(test)
    db.session.commit
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
    return redirect(url_for('admin.tests'))