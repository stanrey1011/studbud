from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from models import User, Test, Question, History
from forms import UserForm, TestForm, QuestionForm, ImportForm, PasswordForm
from extensions import db
from utils import allowed_file, allowed_import_file, create_test_zip, extract_test_zip, save_extracted_images
import os
import json
import re
from io import BytesIO
import sqlite3
from PIL import Image
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

def normalize_image_path(image_path):
    """Normalize image path by removing 'uploads/' prefix if present."""
    if image_path and image_path.startswith('uploads/'):
        return os.path.basename(image_path)
    return image_path

def compress_image(file_path):
    """Compress image to reduce file size while maintaining quality."""
    try:
        img = Image.open(file_path)
        img.thumbnail((800, 600))
        img.save(file_path, optimize=True, quality=85)
        logger.debug(f"Compressed image: {file_path}")
    except Exception as e:
        logger.error(f"Error compressing image {file_path}: {str(e)}")
        raise

@admin_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    """Admin dashboard for user management."""
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
            logger.info(f"Created user: {user.username}")
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
            logger.error(f'Error creating user: {str(e)}')
    return render_template('admin/create_user.html', user_form=user_form, password_form=password_form, users=users)

@admin_bp.route('/tests', methods=['GET', 'POST'])
@login_required
def tests():
    """Manage tests, including import from JSON."""
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
            filename = file.filename.lower()
            
            # Handle ZIP files
            if filename.endswith('.zip'):
                logger.debug(f'Processing ZIP file: {filename}')
                try:
                    # Extract data and images from ZIP
                    data, extracted_images = extract_test_zip(file)
                    
                    # Save extracted images
                    saved_images = save_extracted_images(extracted_images)
                    logger.debug(f'Saved {len(saved_images)} images from ZIP')
                    
                except Exception as e:
                    flash(f'Error processing ZIP file: {str(e)}', 'danger')
                    logger.error(f'ZIP processing error: {str(e)}')
                    return render_template('admin/dashboard.html', tests=tests, import_form=import_form)
            
            # Handle JSON files (original logic)
            elif filename.endswith('.json'):
                logger.debug(f'Processing JSON file: {filename}')
                data = json.load(file)
            
            else:
                flash('Invalid file type. Please upload a JSON or ZIP file.', 'danger')
                return render_template('admin/dashboard.html', tests=tests, import_form=import_form)
            
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
                    logger.debug("Reset SQLite sequence for tests and questions")
                except sqlite3.OperationalError as e:
                    flash(f'Warning: Could not reset sequence: {str(e)}', 'warning')
                    logger.warning(f'Could not reset sequence: {str(e)}')
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
    """Update user password."""
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
        logger.info(f"Updated password for user ID {user_id}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {field}: {error}', 'danger')
                logger.error(f'Password update error for user ID {user_id}: {field} - {error}')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete a user account."""
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
    logger.info(f"Deleted user ID {user_id}")
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/export_tests')
@login_required
def export_tests():
    """Export all tests and questions as ZIP archive with images."""
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    
    tests = Test.query.all()
    data = []
    total_questions = 0
    images_data = {}
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
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
                
                # Collect image files for ZIP
                if q.image:
                    image_path = os.path.join(upload_folder, q.image)
                    if os.path.exists(image_path):
                        images_data[q.image] = image_path
                
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
    
    logger.debug(f'Exported {len(tests)} tests with {total_questions} questions and {len(images_data)} images')
    
    # Create ZIP archive
    zip_output = create_test_zip(data, images_data)
    
    return send_file(zip_output, as_attachment=True, download_name='tests_export.zip', mimetype='application/zip')

@admin_bp.route('/export_test/<int:test_id>')
@login_required
def export_test(test_id):
    """Export a single test and its questions as ZIP archive with images."""
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    
    test = Test.query.get_or_404(test_id)
    questions = []
    images_data = {}
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
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
            
            # Collect image files for ZIP
            if q.image:
                image_path = os.path.join(upload_folder, q.image)
                if os.path.exists(image_path):
                    images_data[q.image] = image_path
            
            questions.append(question_data)
        except json.JSONDecodeError as e:
            logger.warning(f'Skipping question ID {q.id} due to invalid JSON: {str(e)}')
            continue
    
    data = [{
        'test_name': test.name,
        'description': test.description,
        'questions': questions
    }]
    
    logger.debug(f'Exported test "{test.name}" with {len(questions)} questions and {len(images_data)} images')
    
    # Create safe filename from test name
    safe_filename = re.sub(r'[^\w\-_\.]', '_', test.name.lower())
    filename = f'{safe_filename}_export.zip'
    
    # Create ZIP archive
    zip_output = create_test_zip(data, images_data)
    
    return send_file(zip_output, as_attachment=True, download_name=filename, mimetype='application/zip')

@admin_bp.route('/create_test', methods=['GET', 'POST'])
@login_required
def create_test():
    """Create a new test."""
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
        try:
            db.session.commit()
            flash('Test created successfully.', 'success')
            logger.info(f"Created test: {test.name}")
            return redirect(url_for('admin.edit_test', test_id=test.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating test: {str(e)}', 'danger')
            logger.error(f'Error creating test: {str(e)}')
    return render_template('admin/edit_test.html', form=form, q_form=QuestionForm(), questions=[], test=None)

@admin_bp.route('/edit_test/<int:test_id>', methods=['GET', 'POST'])
@login_required
def edit_test(test_id):
    """Edit an existing test and add questions."""
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    test = Test.query.get_or_404(test_id)
    form = TestForm(obj=test)
    q_form = QuestionForm()
    
    # Initialize choices for correct field to prevent validation errors
    q_form.correct.choices = []
    
    # Set appropriate choices for correct field based on question type
    if request.method == 'POST' and 'type' in request.form:
        question_type = request.form.get('type')
        if question_type == 'tf':
            q_form.correct.choices = [('true', 'True'), ('false', 'False')]
        elif question_type in ['mcq', 'mrq']:
            # Parse options to set choices
            options_data = request.form.get('options', '[]')
            try:
                parsed_options = json.loads(options_data)
                if isinstance(parsed_options, list):
                    q_form.correct.choices = [(chr(65 + i), f"{chr(65 + i)}. {opt}") for i, opt in enumerate(parsed_options[:26])]
                else:
                    q_form.correct.choices = []
            except (json.JSONDecodeError, ValueError):
                q_form.correct.choices = []
        elif question_type == 'match':
            # For match questions, we don't need choices for the correct field
            q_form.correct.choices = []
        else:
            q_form.correct.choices = []
    
    if form.validate_on_submit():
        test.name = form.name.data
        test.description = form.description.data
        test.time_limit = form.time_limit.data
        if hasattr(Test, 'num_questions'):
            test.num_questions = form.num_questions.data
        try:
            db.session.commit()
            flash('Test updated successfully.', 'success')
            logger.info(f"Updated test ID {test_id}")
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating test: {str(e)}', 'danger')
            logger.error(f'Error updating test ID {test_id}: {str(e)}')
    if q_form.validate_on_submit():
        logger.debug(f"Form data received: {request.form}")
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
                correct_mappings = json.loads(q_form.match_mappings.data) if q_form.match_mappings.data else {}
                logger.debug(f'Adding question to test ID {test_id}: Terms {terms}, Definitions {definitions}, Mappings {correct_mappings}')
                if len(terms) > 8 or len(definitions) > 8:
                    flash('Maximum of 8 term-definition pairs allowed.', 'danger')
                    return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=test.questions)
                if len(terms) != len(definitions):
                    flash('Terms and definitions must have the same length for match questions.', 'danger')
                    return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=test.questions)
                options = json.dumps({'terms': terms, 'definitions': definitions})
                correct = json.dumps(correct_mappings)
            except json.JSONDecodeError as e:
                flash(f'Invalid JSON format for terms, definitions, or mappings: {str(e)}', 'danger')
                logger.error(f'Invalid JSON in question for test ID {test_id}: {q_form.options.data}, {q_form.match_mappings.data}, error={str(e)}')
                return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=test.questions)
        else:
            options = q_form.options.data if q_form.options.data else '[]'
            correct = ', '.join([ans.strip() for ans in q_form.correct.data]) if q_form.type.data == 'mrq' and q_form.correct.data else q_form.correct.data[0].strip() if q_form.correct.data else ''
            if q_form.type.data in ['mcq', 'tf'] and len(q_form.correct.data) > 1:
                flash('Multiple choice and true/false questions can only have one correct answer.', 'danger')
                return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=test.questions)
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
        try:
            db.session.commit()
            flash('Question added successfully.', 'success')
            logger.info(f"Added question to test ID {test_id}")
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding question: {str(e)}', 'danger')
            logger.error(f'Error adding question to test ID {test_id}: {str(e)}')
            return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=test.questions)
    else:
        for field, errors in q_form.errors.items():
            for error in errors:
                flash(f'Error in adding question - {field}: {error}', 'danger')
                logger.error(f'Form validation error in test ID {test_id}: {field} - {error}')
    questions = Question.query.filter_by(test_id=test_id).all()
    return render_template('admin/edit_test.html', test=test, form=form, q_form=q_form, questions=questions)

@admin_bp.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    """Edit an existing question."""
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    
    question = Question.query.get_or_404(question_id)
    db.session.refresh(question)
    
    # Normalize image path
    normalized_image = normalize_image_path(question.image)
    if normalized_image != question.image:
        question.image = normalized_image
        db.session.commit()
    
    # Initialize variables to pass to the template
    parsed_terms = []
    parsed_definitions = []
    parsed_mappings = {}
    parsed_options = []
    
    # Initialize form
    form = QuestionForm(obj=question)
    
    # Parse existing question data and set form choices
    try:
        if question.type == 'match':
            options = json.loads(question.options or '{}')
            parsed_terms = options.get('terms', [])
            parsed_definitions = options.get('definitions', [])
            parsed_mappings = json.loads(question.correct or '{}')
            logger.debug(f'Loading question ID {question_id}: Terms {parsed_terms}, Definitions {parsed_definitions}, Mappings {parsed_mappings}')
        else:
            parsed_options = json.loads(question.options or '[]')
            
            # Set form choices based on question type
            if question.type == 'tf':
                form.correct.choices = [('true', 'True'), ('false', 'False')]
            elif parsed_options:
                # Try to extract option values (handle "A. Option" format)
                form.correct.choices = []
                for opt in parsed_options:
                    if '.' in opt:
                        value = opt.split('.')[0].strip()
                        label = opt
                    else:
                        value = opt.strip()
                        label = opt.strip()
                    form.correct.choices.append((value, label))
            else:
                form.correct.choices = []
            
            logger.debug(f'Loading question ID {question_id}: Options {parsed_options}, Correct choices {form.correct.choices}')
            
    except json.JSONDecodeError as e:
        flash(f'Invalid JSON data in question options or correct answer: {str(e)}', 'warning')
        logger.warning(f'Invalid JSON in question ID {question_id}: options={question.options}, correct={question.correct}')
    except Exception as e:
        flash(f'Error loading question data: {str(e)}', 'danger')
        logger.error(f'Error loading question ID {question_id}: {str(e)}')
    
    # Set form data for GET requests
    if request.method == 'GET':
        if question.type == 'mrq' and question.correct:
            # Split comma-separated correct answers for MRQ
            correct_answers = [ans.strip() for ans in question.correct.split(', ')] if question.correct else []
            # Extract option keys from full text if needed (for imported questions)
            form.correct.data = []
            for ans in correct_answers:
                # Check if this is a full option text (e.g., "A. Option") or just key (e.g., "A")
                if '.' in ans and any(ans == choice[1] for choice in form.correct.choices):
                    # Find the key for this full option text
                    for value, label in form.correct.choices:
                        if label == ans:
                            form.correct.data.append(value)
                            break
                else:
                    # It's already a key
                    form.correct.data.append(ans)
        elif question.type in ['mcq', 'tf']:
            if question.correct:
                correct_answer = question.correct.strip()
                # Check if this is a full option text (e.g., "A. Option") or just key (e.g., "A")
                if '.' in correct_answer and any(correct_answer == choice[1] for choice in form.correct.choices):
                    # Find the key for this full option text
                    for value, label in form.correct.choices:
                        if label == correct_answer:
                            form.correct.data = [value]
                            break
                else:
                    # It's already a key
                    form.correct.data = [correct_answer]
            else:
                form.correct.data = []
        elif question.type == 'match':
            form.correct.data = json.dumps(parsed_mappings, ensure_ascii=False)
            form.options.data = json.dumps({'terms': parsed_terms, 'definitions': parsed_definitions}, ensure_ascii=False)
        
        logger.debug(f'GET request for question ID {question_id}: form.correct.data={form.correct.data}')
    
    # Handle form submission
    if form.validate_on_submit():
        # DEBUG: Add logging to see what we're receiving
        logger.debug(f"Form data received: {dict(request.form)}")
        logger.debug(f"form.correct.data: {form.correct.data}")
        logger.debug(f"form.type.data: {form.type.data}")
        
        # Handle file upload
        file = form.image.data
        image_path = question.image
        
        # Handle image deletion
        if form.delete_image.data and question.image:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    logger.debug(f"Deleted image: {full_path}")
                    image_path = None
                except Exception as e:
                    flash(f'Error deleting image: {str(e)}', 'danger')
                    logger.error(f'Error deleting image {full_path}: {str(e)}')
        
        # Handle new image upload
        if file and isinstance(file, FileStorage) and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
            compress_image(full_path)
            image_path = filename
        
        # Process form data based on question type
        if form.type.data == 'match':
            try:
                terms = json.loads(form.options.data).get('terms', []) if form.options.data else []
                definitions = json.loads(form.options.data).get('definitions', []) if form.options.data else []
                correct_mappings = json.loads(form.match_mappings.data) if form.match_mappings.data else {}
                
                logger.debug(f'Saving question ID {question_id}: Terms {terms}, Definitions {definitions}, Mappings {correct_mappings}')
                
                # Validation for match questions
                if len(terms) > 8 or len(definitions) > 8:
                    flash('Maximum of 8 term-definition pairs allowed.', 'danger')
                    return render_template('admin/edit_question.html', form=form, question=question,
                                         parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                         parsed_mappings=parsed_mappings, parsed_options=parsed_options)
                
                if len(terms) != len(definitions):
                    flash('Terms and definitions must have the same length for match questions.', 'danger')
                    return render_template('admin/edit_question.html', form=form, question=question,
                                         parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                         parsed_mappings=parsed_mappings, parsed_options=parsed_options)
                
                # Validate mappings
                if not all(str(term['id']) in correct_mappings for term in terms):
                    flash('All terms must have corresponding mappings.', 'danger')
                    return render_template('admin/edit_question.html', form=form, question=question,
                                         parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                         parsed_mappings=parsed_mappings, parsed_options=parsed_options)
                
                # Validate term and definition IDs
                term_ids = set(str(term['id']) for term in terms)
                definition_ids = set(str(definition['id']) for definition in definitions)
                
                for term_id, def_id in correct_mappings.items():
                    if term_id not in term_ids:
                        flash(f'Invalid term ID in mappings: {term_id}', 'danger')
                        return render_template('admin/edit_question.html', form=form, question=question,
                                             parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                             parsed_mappings=parsed_mappings, parsed_options=parsed_options)
                    if def_id not in definition_ids:
                        flash(f'Invalid definition ID in mappings: {def_id}', 'danger')
                        return render_template('admin/edit_question.html', form=form, question=question,
                                             parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                             parsed_mappings=parsed_mappings, parsed_options=parsed_options)
                
                options = json.dumps({'terms': terms, 'definitions': definitions}, ensure_ascii=False)
                correct = json.dumps(correct_mappings, ensure_ascii=False)
                
            except json.JSONDecodeError as e:
                flash(f'Invalid JSON format for terms, definitions, or mappings: {str(e)}', 'danger')
                logger.error(f'Invalid JSON in question ID {question_id}: options={form.options.data}, match_mappings={form.match_mappings.data}')
                return render_template('admin/edit_question.html', form=form, question=question,
                                     parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                     parsed_mappings=parsed_mappings, parsed_options=parsed_options)
        else:
            # Handle non-match question types
            options = form.options.data if form.options.data else '[]'
            
            # Process correct answers based on question type
            if form.type.data == 'mrq' and form.correct.data:
                # For Multiple Response Questions - join selected answers with comma
                correct_answers = [ans.strip() for ans in form.correct.data if ans.strip()]
                correct = ', '.join(correct_answers)
                logger.debug(f'MRQ correct answers: {correct_answers} -> {correct}')
            elif form.correct.data:
                # For single answer questions (MCQ, TF, Flashcard)
                if isinstance(form.correct.data, list):
                    correct = form.correct.data[0].strip() if form.correct.data[0] else ''
                else:
                    correct = form.correct.data.strip()
            else:
                correct = ''
            
            # Validation for single-answer question types
            if form.type.data in ['mcq', 'tf'] and isinstance(form.correct.data, list) and len(form.correct.data) > 1:
                flash('Multiple choice and true/false questions can only have one correct answer.', 'danger')
                return render_template('admin/edit_question.html', form=form, question=question,
                                     parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                     parsed_mappings=parsed_mappings, parsed_options=parsed_options)
        
        # Update question object
        question.type = form.type.data
        question.text = form.text.data
        question.options = options
        question.correct = correct
        question.explanation = form.explanation.data
        question.image = image_path
        
        # Save to database
        try:
            db.session.commit()
            flash('Question updated successfully.', 'success')
            logger.info(f"Updated question ID {question_id}: type={form.type.data}, correct={correct}")
            
            # Update parsed variables after saving for display
            if form.type.data == 'match':
                parsed_terms = json.loads(options).get('terms', [])
                parsed_definitions = json.loads(options).get('definitions', [])
                parsed_mappings = json.loads(correct)
            else:
                parsed_options = json.loads(options)
            
            return redirect(url_for('admin.edit_test', test_id=question.test_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving question: {str(e)}', 'danger')
            logger.error(f'Error saving question ID {question_id}: {str(e)}')
            return render_template('admin/edit_question.html', form=form, question=question,
                                 parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                                 parsed_mappings=parsed_mappings, parsed_options=parsed_options)
    else:
        # Log form validation errors
        if request.method == 'POST':
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error in {field}: {error}', 'danger')
                    logger.error(f'Form validation error in question ID {question_id}: {field} - {error}')
    
    return render_template('admin/edit_question.html', form=form, question=question,
                         parsed_terms=parsed_terms, parsed_definitions=parsed_definitions,
                         parsed_mappings=parsed_mappings, parsed_options=parsed_options)

@admin_bp.route('/instructions')
@login_required
def instructions():
    """Admin instructions page."""
    if not current_user.is_admin:
        flash('Access denied: Admin only.', 'danger')
        return redirect(url_for('user.dashboard'))
    return render_template('admin/instructions.html')

@admin_bp.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    """Delete a question and its associated image."""
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    question = Question.query.get_or_404(question_id)
    test_id = question.test_id
    if question.image:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                logger.debug(f"Deleted image: {full_path}")
            except Exception as e:
                logger.error(f'Error deleting image {full_path}: {str(e)}')
    db.session.delete(question)
    try:
        db.session.commit()
        flash('Question deleted successfully.', 'success')
        logger.info(f"Deleted question ID {question_id}")
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting question: {str(e)}', 'danger')
        logger.error(f'Error deleting question ID {question_id}: {str(e)}')
    return redirect(url_for('admin.edit_test', test_id=test_id))

@admin_bp.route('/delete_test/<int:test_id>', methods=['POST'])
@login_required
def delete_test(test_id):
    """Delete a test and all its questions."""
    if not current_user.is_admin:
        return redirect(url_for('user.dashboard'))
    test = Test.query.get_or_404(test_id)
    for question in test.questions:
        if question.image:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    logger.debug(f"Deleted image: {full_path}")
                except Exception as e:
                    logger.error(f'Error deleting image {full_path}: {str(e)}')
    db.session.delete(test)
    try:
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
                logger.debug("Reset SQLite sequence for tests and questions")
            except sqlite3.OperationalError as e:
                flash(f'Warning: Could not reset sequence: {str(e)}', 'warning')
                logger.warning(f'Could not reset sequence: {str(e)}')
        flash('Test deleted successfully.', 'success')
        logger.info(f"Deleted test ID {test_id}")
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting test: {str(e)}', 'danger')
        logger.error(f'Error deleting test ID {test_id}: {str(e)}')
    return redirect(url_for('admin.tests'))