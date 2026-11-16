from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, ExaminerProfile

auth = Blueprint('auth', __name__)
#login art
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Your account has been deactivated. Contact the administrator.', 'warning')
            return render_template('auth/login.html')
        if user.role == 'examiner' and not user.is_approved:
            flash('Your examiner account is pending admin approval.', 'warning')
            return render_template('auth/login.html')

        session['user_id'] = user.id
        session['user_role'] = user.role
        session['user_name'] = user.full_name

        flash(f'Welcome back, {user.full_name}!', 'success')

        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user.role == 'examiner':
            return redirect(url_for('examiner.dashboard'))
        else:
            return redirect(url_for('student.dashboard'))

    return render_template('auth/login.html')

#logout part
@auth.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

#Registration Part
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name  = request.form.get('full_name', '').strip()
        username   = request.form.get('username', '').strip()
        email      = request.form.get('email', '').strip().lower()
        password   = request.form.get('password', '')
        confirm    = request.form.get('confirm_password', '')
        role       = request.form.get('role', 'student')   # 'student' or 'examiner'
#Validation Check
        if not all([full_name, username, email, password]):
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/register.html')

        if role not in ('student', 'examiner'):
            flash('Invalid role selected.', 'danger')
            return render_template('auth/register.html')
#Unique Check
        if User.query.filter_by(username=username).first():
            flash('Username already taken. Try another.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'danger')
            return render_template('auth/register.html')

#User Creation
        new_user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            role=role,
            is_approved=(role == 'student'),
        )
        db.session.add(new_user)
        db.session.flush() 

        if role == 'examiner':
            profile = ExaminerProfile(
                user_id=new_user.id,
                department=request.form.get('department', '').strip() or None,
                qualification=request.form.get('qualification', '').strip() or None,
            )
            db.session.add(profile)

        db.session.commit()

        if role == 'examiner':
            flash('Registration successful! Please wait for admin approval before logging in.', 'info')
        else:
            flash('Registration successful! You can now log in.', 'success')

        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')
