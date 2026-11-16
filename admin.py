from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash
from models import (
    db, User, ExaminerProfile, Course, Examination,
    ExaminationRubric, ExaminationSlot, Booking
)
from utils import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

#admin dashboard
@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    total_courses = Course.query.count()
    total_exams = Examination.query.count()
    total_examiners = User.query.filter_by(role='examiner').count()
    pending_approvals = User.query.filter_by(role='examiner', is_approved=False).count()
    total_students = User.query.filter_by(role='student').count()
    total_slots = ExaminationSlot.query.count()
    total_bookings = Booking.query.count()

    recent_exams = Examination.query.order_by(Examination.created_at.desc()).limit(5).all()
    recent_bookings = Booking.query.order_by(Booking.booked_at.desc()).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        total_courses=total_courses,
        total_exams=total_exams,
        total_examiners=total_examiners,
        pending_approvals=pending_approvals,
        total_students=total_students,
        total_slots=total_slots,
        total_bookings=total_bookings,
        recent_exams=recent_exams,
        recent_bookings=recent_bookings
    )

#course manage
@admin_bp.route('/courses')
@role_required('admin')
def manage_courses():
    search_query = request.args.get('q', '').strip()
    if search_query:
        courses = Course.query.filter(
            (Course.course_code.ilike(f'%{search_query}%')) |
            (Course.course_name.ilike(f'%{search_query}%'))
        ).order_by(Course.course_code.asc()).all()
    else:
        courses = Course.query.order_by(Course.created_at.desc()).all()

    return render_template('admin/courses.html', courses=courses, search_query=search_query)


@admin_bp.route('/courses/add', methods=['GET', 'POST'])
@role_required('admin')
def add_course():
    if request.method == 'POST':
        code = request.form.get('course_code', '').strip().upper()
        name = request.form.get('course_name', '').strip()
        description = request.form.get('description', '').strip()

        if not code or not name:
            flash('Course Code and Course Name are required.', 'danger')
            return render_template('admin/add_course.html')

        if Course.query.filter_by(course_code=code).first():
            flash(f'Course code "{code}" already exists.', 'danger')
            return render_template('admin/add_course.html')

        course = Course(course_code=code, course_name=name, description=description or None)
        db.session.add(course)
        db.session.commit()
        flash(f'Course {code} ({name}) created successfully!', 'success')
        return redirect(url_for('admin.manage_courses'))

    return render_template('admin/add_course.html')


@admin_bp.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        code = request.form.get('course_code', '').strip().upper()
        name = request.form.get('course_name', '').strip()
        description = request.form.get('description', '').strip()

        if not code or not name:
            flash('Course Code and Course Name are required.', 'danger')
            return render_template('admin/edit_course.html', course=course)

        existing = Course.query.filter_by(course_code=code).first()
        if existing and existing.id != course.id:
            flash(f'Course code "{code}" already in use by another course.', 'danger')
            return render_template('admin/edit_course.html', course=course)

        course.course_code = code
        course.course_name = name
        course.description = description or None
        db.session.commit()
        flash(f'Course {code} updated successfully!', 'success')
        return redirect(url_for('admin.manage_courses'))

    return render_template('admin/edit_course.html', course=course)


@admin_bp.route('/courses/<int:course_id>/delete', methods=['POST'])
@role_required('admin')
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    code = course.course_code
    db.session.delete(course)
    db.session.commit()
    flash(f'Course {code} and all associated exams/slots were deleted.', 'info')
    return redirect(url_for('admin.manage_courses'))

#exam manage
@admin_bp.route('/examinations')
@role_required('admin')
def manage_examinations():
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Examination.query
    if search_query:
        query = query.filter(Examination.title.ilike(f'%{search_query}%'))
    if status_filter:
        query = query.filter_by(status=status_filter)

    examinations = query.order_by(Examination.created_at.desc()).all()
    return render_template(
        'admin/examinations.html',
        examinations=examinations,
        search_query=search_query,
        status_filter=status_filter
    )


@admin_bp.route('/examinations/add', methods=['GET', 'POST'])
@role_required('admin')
def add_examination():
    courses = Course.query.order_by(Course.course_code.asc()).all()
    if not courses:
        flash('Please add at least one course before creating an examination.', 'warning')
        return redirect(url_for('admin.add_course'))

    if request.method == 'POST':
        course_id = request.form.get('course_id', type=int)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        total_marks = request.form.get('total_marks', type=int) or 100
        status = request.form.get('status', 'Draft')

        def parse_dt(field_name):
            val = request.form.get(field_name)
            if val:
                try:
                    return datetime.strptime(val, '%Y-%m-%dT%H:%M')
                except ValueError:
                    pass
            return None

        exam = Examination(
            course_id=course_id,
            title=title,
            description=description or None,
            total_marks=total_marks,
            status=status,
            slot_creation_start=parse_dt('slot_creation_start'),
            slot_creation_end=parse_dt('slot_creation_end'),
            booking_start=parse_dt('booking_start'),
            booking_end=parse_dt('booking_end'),
            exam_date=parse_dt('exam_date')
        )
        db.session.add(exam)
        db.session.commit()
        flash(f'Examination "{title}" created successfully! Now add rubrics.', 'success')
        return redirect(url_for('admin.manage_rubrics', exam_id=exam.id))

    return render_template('admin/add_examination.html', courses=courses)


@admin_bp.route('/examinations/<int:exam_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_examination(exam_id):
    exam = Examination.query.get_or_404(exam_id)
    courses = Course.query.order_by(Course.course_code.asc()).all()

    if request.method == 'POST':
        exam.course_id = request.form.get('course_id', type=int)
        exam.title = request.form.get('title', '').strip()
        exam.description = request.form.get('description', '').strip()
        exam.total_marks = request.form.get('total_marks', type=int) or 100
        exam.status = request.form.get('status', 'Draft')

        def parse_dt(field_name):
            val = request.form.get(field_name)
            if val:
                try:
                    return datetime.strptime(val, '%Y-%m-%dT%H:%M')
                except ValueError:
                    pass
            return None

        exam.slot_creation_start = parse_dt('slot_creation_start')
        exam.slot_creation_end = parse_dt('slot_creation_end')
        exam.booking_start = parse_dt('booking_start')
        exam.booking_end = parse_dt('booking_end')
        exam.exam_date = parse_dt('exam_date')

        db.session.commit()
        flash(f'Examination "{exam.title}" updated successfully!', 'success')
        return redirect(url_for('admin.manage_examinations'))

    return render_template('admin/edit_examination.html', exam=exam, courses=courses)


@admin_bp.route('/examinations/<int:exam_id>/update-status', methods=['POST'])
@role_required('admin')
def update_examination_status(exam_id):
    exam = Examination.query.get_or_404(exam_id)
    new_status = request.form.get('status')
    valid_statuses = ['Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed']
    if new_status in valid_statuses:
        exam.status = new_status
        db.session.commit()
        flash(f'Status for "{exam.title}" changed to {new_status}.', 'success')
    else:
        flash('Invalid status supplied.', 'danger')
    return redirect(request.referrer or url_for('admin.manage_examinations'))


@admin_bp.route('/examinations/<int:exam_id>/delete', methods=['POST'])
@role_required('admin')
def delete_examination(exam_id):
    exam = Examination.query.get_or_404(exam_id)
    title = exam.title
    db.session.delete(exam)
    db.session.commit()
    flash(f'Examination "{title}" deleted.', 'info')
    return redirect(url_for('admin.manage_examinations'))

#exam rubric management
@admin_bp.route('/examinations/<int:exam_id>/rubrics', methods=['GET', 'POST'])
@role_required('admin')
def manage_rubrics(exam_id):
    exam = Examination.query.get_or_404(exam_id)

    if request.method == 'POST':
        criterion_name = request.form.get('criterion_name', '').strip()
        max_marks = request.form.get('max_marks', type=int)
        description = request.form.get('description', '').strip()

        if not criterion_name or max_marks is None or max_marks <= 0:
            flash('Valid criterion name and positive maximum marks are required.', 'danger')
        else:
            rubric = ExaminationRubric(
                examination_id=exam.id,
                criterion_name=criterion_name,
                max_marks=max_marks,
                description=description or None
            )
            db.session.add(rubric)
            db.session.commit()
            flash(f'Rubric criterion "{criterion_name}" added ({max_marks} marks).', 'success')
            return redirect(url_for('admin.manage_rubrics', exam_id=exam.id))

    current_total = sum(r.max_marks for r in exam.rubrics)
    return render_template(
        'admin/manage_rubrics.html',
        exam=exam,
        current_total=current_total
    )


@admin_bp.route('/rubrics/<int:rubric_id>/delete', methods=['POST'])
@role_required('admin')
def delete_rubric(rubric_id):
    rubric = ExaminationRubric.query.get_or_404(rubric_id)
    exam_id = rubric.examination_id
    db.session.delete(rubric)
    db.session.commit()
    flash(f'Rubric criterion "{rubric.criterion_name}" deleted.', 'info')
    return redirect(url_for('admin.manage_rubrics', exam_id=exam_id))

#user and exam manage
@admin_bp.route('/users')
@role_required('admin')
def manage_users():
    search_query = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()

    query = User.query.filter(User.role != 'admin')
    if search_query:
        query = query.filter(
            (User.full_name.ilike(f'%{search_query}%')) |
            (User.username.ilike(f'%{search_query}%')) |
            (User.email.ilike(f'%{search_query}%'))
        )
    if role_filter:
        query = query.filter_by(role=role_filter)

    users = query.order_by(User.created_at.desc()).all()
    examiners = [u for u in users if u.role == 'examiner']
    students = [u for u in users if u.role == 'student']

    return render_template(
        'admin/users.html',
        examiners=examiners,
        students=students,
        search_query=search_query,
        role_filter=role_filter
    )


@admin_bp.route('/examiners/add', methods=['GET', 'POST'])
@role_required('admin')
def add_examiner():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        department = request.form.get('department', '').strip()
        qualification = request.form.get('qualification', '').strip()
        bio = request.form.get('bio', '').strip()

        if not all([full_name, username, email, password]):
            flash('All primary fields (Name, Username, Email, Password) are required.', 'danger')
            return render_template('admin/add_examiner.html')

        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'danger')
            return render_template('admin/add_examiner.html')

        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'danger')
            return render_template('admin/add_examiner.html')

        examiner = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            role='examiner',
            is_approved=True  # Directly created by Admin, so pre-approved
        )
        db.session.add(examiner)
        db.session.flush()

        profile = ExaminerProfile(
            user_id=examiner.id,
            department=department or None,
            qualification=qualification or None,
            bio=bio or None
        )
        db.session.add(profile)
        db.session.commit()

        flash(f'Examiner {full_name} added and approved successfully!', 'success')
        return redirect(url_for('admin.manage_users'))

    return render_template('admin/add_examiner.html')


@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@role_required('admin')
def approve_examiner(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != 'examiner':
        flash('Only examiners can be approved.', 'warning')
        return redirect(url_for('admin.manage_users'))

    user.is_approved = True
    db.session.commit()
    flash(f'Examiner "{user.full_name}" is now approved to log in and manage slots.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@role_required('admin')
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Admin account cannot be deactivated.', 'danger')
        return redirect(url_for('admin.manage_users'))

    user.is_active = not user.is_active
    db.session.commit()
    state = "activated" if user.is_active else "deactivated"
    flash(f'User "{user.full_name}" has been {state}.', 'info')
    return redirect(url_for('admin.manage_users'))


#exam slots
@admin_bp.route('/slots')
@role_required('admin')
def manage_slots():
    exam_id = request.args.get('exam_id', type=int)
    examiner_id = request.args.get('examiner_id', type=int)

    query = ExaminationSlot.query
    if exam_id:
        query = query.filter_by(examination_id=exam_id)
    if examiner_id:
        query = query.filter_by(examiner_id=examiner_id)

    slots = query.order_by(ExaminationSlot.slot_date.desc(), ExaminationSlot.start_time.asc()).all()
    examinations = Examination.query.all()
    examiners = User.query.filter_by(role='examiner', is_approved=True, is_active=True).all()

    return render_template(
        'admin/slots.html',
        slots=slots,
        examinations=examinations,
        examiners=examiners,
        selected_exam_id=exam_id,
        selected_examiner_id=examiner_id
    )


@admin_bp.route('/slots/<int:slot_id>/change-examiner', methods=['POST'])
@role_required('admin')
def change_slot_examiner(slot_id):
    slot = ExaminationSlot.query.get_or_404(slot_id)
    new_examiner_id = request.form.get('new_examiner_id', type=int)

    new_examiner = User.query.filter_by(id=new_examiner_id, role='examiner', is_approved=True).first()
    if not new_examiner:
        flash('Selected examiner is invalid or unapproved.', 'danger')
        return redirect(url_for('admin.manage_slots'))

    old_name = slot.examiner.full_name
    slot.examiner_id = new_examiner.id
    db.session.commit()
    flash(f'Assigned examiner for slot ({slot.slot_date} {slot.start_time}) changed from {old_name} to {new_examiner.full_name}.', 'success')
    return redirect(url_for('admin.manage_slots'))



@admin_bp.route('/bookings')
@role_required('admin')
def manage_bookings():
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Booking.query.join(User, Booking.student_id == User.id)
    if search_query:
        query = query.filter(
            (User.full_name.ilike(f'%{search_query}%')) |
            (User.username.ilike(f'%{search_query}%')) |
            (User.email.ilike(f'%{search_query}%'))
        )
    if status_filter:
        query = query.filter(Booking.status == status_filter)

    bookings = query.order_by(Booking.booked_at.desc()).all()
    # Available slots for rescheduling
    available_slots = ExaminationSlot.query.filter_by(is_closed=False).all()

    return render_template(
        'admin/bookings.html',
        bookings=bookings,
        available_slots=available_slots,
        search_query=search_query,
        status_filter=status_filter
    )


@admin_bp.route('/bookings/<int:booking_id>/reschedule', methods=['POST'])
@role_required('admin')
def reschedule_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_slot_id = request.form.get('new_slot_id', type=int)

    new_slot = ExaminationSlot.query.get_or_404(new_slot_id)
    if not new_slot.is_available():
        flash('Cannot reschedule: Target slot is full or closed.', 'danger')
        return redirect(url_for('admin.manage_bookings'))

    old_slot_info = f"{booking.slot.slot_date} ({booking.slot.start_time})"
    booking.slot_id = new_slot.id
    db.session.commit()

    flash(f'Booking for {booking.student.full_name} rescheduled from {old_slot_info} to {new_slot.slot_date} ({new_slot.start_time}).', 'success')
    return redirect(url_for('admin.manage_bookings'))
