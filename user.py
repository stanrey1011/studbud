from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import Test, Question, History
from forms import SimStartForm
from extensions import db
from utils import calculate_score
import time
import random
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    tests = Test.query.all()
    sim_form = SimStartForm()
    return render_template('user/dashboard.html', tests=tests, sim_form=sim_form)

@user_bp.route('/quiz/<int:test_id>/<string:mode>', methods=['GET', 'POST'])
@login_required
def quiz(test_id, mode):
    if mode not in ['study', 'sim', 'flashcard']:
        flash('Invalid mode.', 'danger')
        return redirect(url_for('user.dashboard'))
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    total_questions = len(questions)

    if mode == 'study':
        if request.method == 'POST':
            try:
                data = request.json
                answers = data.get('answers', {})
                question_id = data.get('question_id')
                score = 0
                if question_id:
                    question = next((q for q in questions if q.id == int(question_id)), None)
                    if question:
                        if question.type == 'match':
                            correct_mappings = json.loads(question.correct or '{}')
                            score = sum(1 for term_id, def_id in answers.items()
                                        if correct_mappings.get(term_id) == def_id) / len(correct_mappings) if correct_mappings else 0.0
                        else:
                            user_ans = answers.get(str(question.id))
                            if question.type == 'mrq':
                                correct = question.correct.split(', ') if question.correct else []
                                user_ans = user_ans if isinstance(user_ans, list) else []
                                score = 1 if sorted(correct) == sorted(user_ans) else 0
                            elif question.type == 'tf':
                                score = 1 if str(user_ans).lower() == str(question.correct).lower() else 0
                            else:
                                score = 1 if user_ans == question.correct else 0
                        history = History(
                            user_id=current_user.id,
                            test_id=test_id,
                            mode=mode,
                            score=score,
                            answers=json.dumps({str(question_id): answers})
                        )
                        db.session.add(history)
                        db.session.commit()
                        return jsonify({'status': 'saved', 'score': score, 'correct': json.loads(question.correct) if question.type == 'match' else question.correct})
                return jsonify({'status': 'error', 'message': 'Invalid question ID'}), 400
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 400
        for q in questions:
            if q.type == 'match':
                options = json.loads(q.options or '{}')
                q.parsed_terms = options.get('terms', [])
                q.parsed_definitions = options.get('definitions', [])
                q.parsed_mappings = json.loads(q.correct or '{}')
                # Validate mappings
                valid_def_ids = {str(definition['id']) for definition in q.parsed_definitions}
                original_mappings = q.parsed_mappings.copy()
                q.parsed_mappings = {k: v for k, v in q.parsed_mappings.items() if k in valid_def_ids and v in valid_def_ids}
                if len(q.parsed_mappings) < len(original_mappings):
                    flash(f'Warning: Some mappings for question ID {q.id} were invalid and filtered out.', 'warning')
                    logger.debug(f'Question ID {q.id}: Original mappings {original_mappings}, Valid mappings {q.parsed_mappings}, Terms {q.parsed_terms}, Definitions {q.parsed_definitions}')
            else:
                q.parsed_options = json.loads(q.options or '[]')
        return render_template('user/study_mode.html', test=test, questions=questions, mode=mode)
    
    # Flashcard mode
    if mode == 'flashcard':
        if request.method == 'POST':
            try:
                data = request.json
                score = data.get('score', 0)
                question_id = data.get('question_id')
                
                if question_id:
                    history = History(
                        user_id=current_user.id,
                        test_id=test_id,
                        mode=mode,
                        score=score,
                        answers=json.dumps({str(question_id): 'reviewed'})
                    )
                    db.session.add(history)
                    db.session.commit()
                    return jsonify({'status': 'saved'})
                return jsonify({'status': 'error', 'message': 'Invalid question ID'}), 400
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 400
        
        # Prepare questions for flashcard mode
        for q in questions:
            if q.type == 'match':
                options = json.loads(q.options or '{}')
                q.parsed_terms = options.get('terms', [])
                q.parsed_definitions = options.get('definitions', [])
                q.parsed_mappings = json.loads(q.correct or '{}')
            else:
                q.parsed_options = json.loads(q.options or '[]')
        return render_template('user/flashcard_mode.html', test=test, questions=questions, mode=mode)

    # Simulation mode configuration from dashboard
    config_phase = 'sim_progress' not in session or session['sim_progress'].get('test_id') != test_id
    if config_phase:
        form = SimStartForm()
        if request.method == 'POST' and form.validate_on_submit():
            custom_time = form.custom_time.data or 0
            num_questions = int(request.form.get('num_questions', total_questions))
            if 1 <= num_questions <= total_questions:
                selected_questions = random.sample(questions, num_questions)
                effective_time_limit = custom_time * 60
                session['sim_progress'] = {
                    'test_id': test_id,
                    'current': 0,
                    'answers': {},
                    'start_time': time.time(),
                    'time_limit': effective_time_limit,
                    'questions': [q.id for q in selected_questions]
                }
                return redirect(url_for('user.quiz', test_id=test_id, mode='sim'))
            else:
                flash('Number of questions must be between 1 and the total available.', 'danger')
        return render_template('user/simulation_mode.html', test=test, form=form, total_questions=total_questions, config_phase=config_phase, test_id=test_id)
    else:
        progress = session.get('sim_progress', {'answers': {}})
        if not progress or progress.get('test_id') != test_id:
            flash('Simulation session invalid or stopped. Please start a new simulation.', 'danger')
            return redirect(url_for('user.dashboard'))
        time_limit = progress.get('time_limit', 0)
        start_time = progress.get('start_time', time.time())
        elapsed = time.time() - start_time
        remaining_seconds = max(0, time_limit - elapsed) if time_limit > 0 else None

        if time_limit > 0 and elapsed > time_limit:
            score = calculate_score([q for q in questions if q.id in progress.get('questions', [])], progress.get('answers', {}))
            history = History(
                user_id=current_user.id,
                test_id=test_id,
                mode=mode,
                score=score,
                answers=json.dumps(progress.get('answers', {}))
            )
            db.session.add(history)
            db.session.commit()
            session.pop('sim_progress', None)
            flash('Time up! Test submitted.', 'info')
            return render_template('user/results.html', score=score, total=len(progress.get('questions', [])), elapsed=elapsed, test=test)

        if request.method == 'POST' and 'question_id' in request.form:
            q_id = request.form.get('question_id')
            if q_id:
                question = next((q for q in questions if q.id == int(q_id)), None)
                if question:
                    if question.type == 'match':
                        answer = {key: value for key, value in request.form.items() if key.startswith('term_')}
                        answer = {k.replace('term_', ''): v for k, v in answer.items() if v}
                    else:
                        answer = request.form.getlist('correct') if question.type == 'mrq' else request.form.get('correct')
                    progress.setdefault('answers', {})[q_id] = answer

            if 'next' in request.form and progress.get('current', 0) < len(progress.get('questions', [])) - 1:
                progress['current'] = progress.get('current', 0) + 1
            elif 'prev' in request.form and progress.get('current', 0) > 0:
                progress['current'] = progress.get('current', 0) - 1
            elif 'submit' in request.form or (time_limit > 0 and elapsed > time_limit):
                score = calculate_score([q for q in questions if q.id in progress.get('questions', [])], progress.get('answers', {}))
                history = History(
                    user_id=current_user.id,
                    test_id=test_id,
                    mode=mode,
                    score=score,
                    answers=json.dumps(progress.get('answers', {}))
                )
                db.session.add(history)
                db.session.commit()
                session.pop('sim_progress', None)
                return render_template('user/results.html', score=score, total=len(progress.get('questions', [])), elapsed=elapsed, test=test)
            session['sim_progress'] = progress

        current_question = next((q for q in questions if q.id == progress.get('questions', [0])[progress.get('current', 0)]), None)
        if current_question is None:
            flash('Error: Could not find current question.', 'danger')
            return redirect(url_for('user.dashboard'))
        if current_question.type == 'match':
            options = json.loads(current_question.options or '{}')
            current_question.parsed_terms = options.get('terms', [])
            current_question.parsed_definitions = options.get('definitions', [])
            current_question.parsed_mappings = json.loads(current_question.correct or '{}')
            # Validate mappings
            valid_def_ids = {str(definition['id']) for definition in current_question.parsed_definitions}
            original_mappings = current_question.parsed_mappings.copy()
            current_question.parsed_mappings = {k: v for k, v in current_question.parsed_mappings.items() if k in valid_def_ids and v in valid_def_ids}
            if len(current_question.parsed_mappings) < len(original_mappings):
                flash(f'Warning: Some mappings for question ID {current_question.id} were invalid and filtered out.', 'warning')
                logger.debug(f'Simulation mode - Question ID {current_question.id}: Original mappings {original_mappings}, Valid mappings {current_question.parsed_mappings}, Terms {current_question.parsed_terms}, Definitions {current_question.parsed_definitions}')
        else:
            current_question.parsed_options = json.loads(current_question.options or '[]')
        selected = progress.get('answers', {}).get(str(current_question.id), {} if current_question.type == 'match' else [])

        return render_template(
            'user/simulation_mode.html',
            test=test,
            question=current_question,
            options=current_question.parsed_options if current_question.type != 'match' else current_question.parsed_definitions,
            terms=current_question.parsed_terms if current_question.type == 'match' else [],
            current=progress.get('current', 0) + 1,
            total=len(progress.get('questions', [])),
            time_limit=time_limit,
            start_time=start_time,
            selected=selected,
            config_phase=False,
            test_id=test_id
        )

@user_bp.route('/stop_simulation/<int:test_id>', methods=['POST'])
@login_required
def stop_simulation(test_id):
    if 'sim_progress' in session:
        session.pop('sim_progress', None)
        flash('Simulation stopped. Session cleared.', 'success')
    return redirect(url_for('user.dashboard', _external=True))

@user_bp.route('/instructions')
@login_required
def instructions():
    """User instructions page."""
    return render_template('user/instructions.html')

@user_bp.route('/history')
@login_required
def history():
    histories = History.query.filter_by(user_id=current_user.id).order_by(History.date.desc()).all()
    return render_template('user/history.html', histories=histories)