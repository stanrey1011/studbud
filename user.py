from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import Test, Question, History
from forms import SimStartForm
from extensions import db
from utils import calculate_score
import time
import random
import json

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
    if mode not in ['study', 'sim']:
        flash('Invalid mode.', 'danger')
        return redirect(url_for('user.dashboard'))
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    total_questions = len(questions)

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
                answer = request.form.getlist('correct') if request.form.get('question_type') == 'mrq' else request.form.get('correct')
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
        options_list = json.loads(current_question.options) if current_question.options else []
        selected = progress.get('answers', {}).get(str(current_question.id), [])

        return render_template(
            'user/simulation_mode.html',
            test=test,
            question=current_question,
            options=options_list,
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

@user_bp.route('/history')
@login_required
def history():
    histories = History.query.filter_by(user_id=current_user.id).order_by(History.date.desc()).all()
    return render_template('user/history.html', histories=histories)