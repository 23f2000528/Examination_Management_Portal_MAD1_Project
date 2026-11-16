from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from models import db, User, Examination, ExaminationSlot, Booking, Course
from utils import role_required

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard')
@role_required('student')
def dashboard():
    student_id = session['user_id']
    student = User.query.get(student_id)

    all_bookings = Booking.query.filter_by(student_id=student_id).order_by(Booking.booked_at.desc()).all()

    upcoming_bookings = []
    past_bookings = []

    for booking in all_bookings:
        if booking.status == 'Booked':
            upcoming_bookings.append(booking)
        else:
            past_bookings.append(booking)

    now = datetime.utcnow()
    all_exams = Examination.query.all()
    available_exams = []

    for examination in all_exams:
        if examination.status == 'Booking Open':
            if examination.booking_start and examination.booking_end:
                if examination.booking_start <= now and now <= examination.booking_end:
                    available_exams.append(examination)
            else:
                available_exams.append(examination)

    return render_template(
        'student/dashboard.html',
        student=student,
        upcoming_bookings=upcoming_bookings,
        past_bookings=past_bookings,
        available_exams=available_exams
    )


@student_bp.route('/profile', methods=['GET', 'POST'])
@role_required('student')
def profile():
    student_id = session['user_id']
    student = User.query.get(student_id)

    if request.method == 'POST':
        student.full_name = request.form.get('full_name')
        db.session.commit()
        session['user_name'] = student.full_name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.dashboard'))

    return render_template('student/profile.html', student=student)


@student_bp.route('/examinations')
@role_required('student')
def view_examinations():
    search_query = request.args.get('q', '').strip()
    course_id = request.args.get('course_id', type=int)

    now = datetime.utcnow()
    all_exams = Examination.query.all()
    filtered_exams = []

    for examination in all_exams:
        if examination.status in ['Booking Open', 'Slot Creation']:
            match_search = True
            if search_query:
                if search_query.lower() not in examination.title.lower():
                    match_search = False

            match_course = True
            if course_id:
                if examination.course_id != course_id:
                    match_course = False

            if match_search and match_course:
                filtered_exams.append(examination)

    courses = Course.query.all()

    return render_template(
        'student/examinations.html',
        examinations=filtered_exams,
        courses=courses,
        search_query=search_query,
        selected_course_id=course_id,
        current_time=now
    )


@student_bp.route('/examinations/<int:exam_id>/slots')
@role_required('student')
def view_slots(exam_id):
    student_id = session['user_id']
    examination = Examination.query.get(exam_id)

    now = datetime.utcnow()

    existing_booking = None
    for slot in examination.slots:
        for booking in slot.bookings:
            if booking.student_id == student_id and booking.status == 'Booked':
                existing_booking = booking

    return render_template(
        'student/slots.html',
        examination=examination,
        existing_booking=existing_booking,
        current_time=now
    )


@student_bp.route('/slots/<int:slot_id>/book', methods=['POST'])
@role_required('student')
def book_slot(slot_id):
    student_id = session['user_id']
    slot = ExaminationSlot.query.get(slot_id)
    examination = slot.examination
    now = datetime.utcnow()

    if examination.status != 'Booking Open':
        flash('Student slot booking is closed for this examination.', 'danger')
        return redirect(url_for('student.view_slots', exam_id=examination.id))

    if examination.booking_start and now < examination.booking_start:
        flash('Student slot booking has not started yet.', 'danger')
        return redirect(url_for('student.view_slots', exam_id=examination.id))

    if examination.booking_end and now > examination.booking_end:
        flash('Student slot booking deadline has passed.', 'danger')
        return redirect(url_for('student.view_slots', exam_id=examination.id))

    for existing_slot in examination.slots:
        for booking in existing_slot.bookings:
            if booking.student_id == student_id and booking.status in ['Booked', 'Completed']:
                flash('Duplicate booking prevented: You already have a booking for this examination.', 'danger')
                return redirect(url_for('student.view_slots', exam_id=examination.id))

    if not slot.is_available():
        flash('This examination slot is already full.', 'danger')
        return redirect(url_for('student.view_slots', exam_id=examination.id))

    new_booking = Booking(
        student_id=student_id,
        slot_id=slot.id,
        status='Booked'
    )
    db.session.add(new_booking)
    db.session.commit()

    if slot.booked_count() >= slot.capacity:
        slot.is_closed = True
        db.session.commit()

    flash('Slot booked successfully!', 'success')
    return redirect(url_for('student.dashboard'))


@student_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@role_required('student')
def cancel_booking(booking_id):
    student_id = session['user_id']
    booking = Booking.query.get(booking_id)

    if booking.student_id != student_id:
        flash('You can only cancel your own bookings.', 'danger')
        return redirect(url_for('student.dashboard'))

    if booking.status != 'Booked':
        flash('Only active bookings can be cancelled.', 'danger')
        return redirect(url_for('student.dashboard'))

    now = datetime.utcnow()
    examination = booking.slot.examination

    if examination.booking_end and now > examination.booking_end:
        flash('Booking deadline has passed. Cancellation is no longer permitted.', 'danger')
        return redirect(url_for('student.dashboard'))

    booking.status = 'Cancelled'

    slot = booking.slot
    if slot.is_closed and slot.booked_count() < slot.capacity:
        slot.is_closed = False

    db.session.commit()
    flash('Booking cancelled successfully.', 'info')
    return redirect(url_for('student.dashboard'))


@student_bp.route('/bookings/<int:booking_id>/result')
@role_required('student')
def view_result(booking_id):
    student_id = session['user_id']
    booking = Booking.query.get(booking_id)

    if booking.student_id != student_id:
        flash('You can only view your own examination results.', 'danger')
        return redirect(url_for('student.dashboard'))

    return render_template('student/result.html', booking=booking)


@student_bp.route('/history')
@role_required('student')
def booking_history():
    student_id = session['user_id']
    student = User.query.get(student_id)

    status_filter = request.args.get('status', '').strip()

    all_bookings = Booking.query.filter_by(student_id=student_id).order_by(Booking.booked_at.desc()).all()

    if status_filter:
        filtered_bookings = []
        for b in all_bookings:
            if b.status == status_filter:
                filtered_bookings.append(b)
    else:
        filtered_bookings = all_bookings

    return render_template(
        'student/history.html',
        student=student,
        bookings=filtered_bookings,
        status_filter=status_filter
    )

