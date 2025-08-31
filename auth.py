from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from models import User
from forms import LoginForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('auth.admin_instructions'))
        else:
            return redirect(url_for('auth.user_instructions'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('auth.admin_instructions' if user.is_admin else 'auth.user_instructions'))
        flash('Invalid username or password.', 'danger')
    return render_template('admin/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/admin/instructions')
@login_required
def admin_instructions():
    if not current_user.is_admin:
        return redirect(url_for('auth.user_instructions'))
    return render_template('admin/instructions.html')

@auth_bp.route('/user/instructions')
@login_required
def user_instructions():
    return render_template('user/instructions.html')