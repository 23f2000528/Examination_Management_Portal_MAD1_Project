from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from models import db, User, ExaminerProfile, Examination, ExaminationRubric, ExaminationSlot, Booking, EvaluationScore
from utils import role_required

examiner_bp = Blueprint('examiner', __name__, url_prefix='/examiner')


@examiner_bp.route('/dashboard')
@role_required('examiner')
def dashboard():
    examiner_id = session['user_id']
    examiner = User.query.get(examiner_id)

    active_exams = Examination.query.filter(
        Examination.status.in_(['Slot Creation', 'Booking Open', 'Closed'])
    ).all()

    my_slots = ExaminationSlot.query.filter_by(examiner_id=examiner_id).all()

    total_booked = 0
    pending_evaluations = 0
    completed_evaluations = 0

    for slot in my_slots:
        for booking in slot.bookings:
            if booking.status != 'Cancelled':
                total_booked = total_booked + 1
                if booking.status == 'Booked':
                    pending_evaluations = pending_evaluations + 1
                elif booking.status == 'Completed':
                    completed_evaluations = completed_evaluations + 1

    return render_template(
        'examiner/dashboard.html',
        examiner=examiner,
        active_exams=active_exams,
        my_slots=my_slots,
        total_booked=total_booked,
        pending_evaluations=pending_evaluations,
        completed_evaluations=completed_evaluations
    )


@examiner_bp.route('/profile', methods=['GET', 'POST'])
@role_required('examiner')
def profile():
    examiner_id = session['user_id']
    user = User.query.get(examiner_id)

    if not user.examiner_profile:
        new_profile = ExaminerProfile(user_id=user.id)
        db.session.add(new_profile)
        db.session.commit()

    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.examiner_profile.department = request.form.get('department')
        user.examiner_profile.qualification = request.form.get('qualification')
        user.examiner_profile.bio = request.form.get('bio')

        db.session.commit()
        session['user_name'] = user.full_name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('examiner.dashboard'))

    return render_template('examiner/profile.html', user=user)


@examiner_bp.route('/slots/create', methods=['GET', 'POST'])
@role_required('examiner')
def create_slot():
    examiner_id = session['user_id']
    now = datetime.utcnow()

    all_exams = Examination.query.all()
    eligible_exams = []

    for exam in all_exams:
        if exam.status == 'Slot Creation':
            if exam.slot_creation_start and exam.slot_creation_end:
                if exam.slot_creation_start <= now and now <= exam.slot_creation_end:
                    eligible_exams.append(exam)
            else:
                eligible_exams.append(exam)

    if request.method == 'POST':
        examination_id = int(request.form.get('examination_id'))
        slot_date_string = request.form.get('slot_date')
        start_time_string = request.form.get('start_time')
        end_time_string = request.form.get('end_time')
        capacity = int(request.form.get('capacity', 1))

        exam = Examination.query.get(examination_id)

        if exam.slot_creation_start and now < exam.slot_creation_start:
            flash('Slot creation has not started yet for this exam.', 'danger')
            return redirect(url_for('examiner.create_slot'))

        if exam.slot_creation_end and now > exam.slot_creation_end:
            flash('Slot creation period is over for this exam.', 'danger')
            return redirect(url_for('examiner.create_slot'))

        slot_date = datetime.strptime(slot_date_string, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_string, '%H:%M').time()
        end_time = datetime.strptime(end_time_string, '%H:%M').time()

        if start_time >= end_time:
            flash('Start time must be before end time.', 'danger')
            return render_template('examiner/create_slot.html', eligible_exams=eligible_exams)

        new_slot = ExaminationSlot(
            examination_id=examination_id,
            examiner_id=examiner_id,
            slot_date=slot_date,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            is_closed=False
        )
        db.session.add(new_slot)
        db.session.commit()

        flash('Slot created successfully!', 'success')
        return redirect(url_for('examiner.dashboard'))

    return render_template('examiner/create_slot.html', eligible_exams=eligible_exams)


@examiner_bp.route('/slots/<int:slot_id>/edit', methods=['GET', 'POST'])
@role_required('examiner')
def edit_slot(slot_id):
    examiner_id = session['user_id']
    slot = ExaminationSlot.query.get(slot_id)

    if slot.examiner_id != examiner_id:
        flash('You cannot edit slots created by other examiners.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    if slot.booked_count() > 0:
        flash('Students have already booked this slot. You cannot edit it.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    now = datetime.utcnow()
    if slot.examination.booking_start and now >= slot.examination.booking_start:
        flash('Student booking has already started. You cannot edit this slot.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    if request.method == 'POST':
        slot_date_string = request.form.get('slot_date')
        start_time_string = request.form.get('start_time')
        end_time_string = request.form.get('end_time')
        capacity = int(request.form.get('capacity', 1))

        slot.slot_date = datetime.strptime(slot_date_string, '%Y-%m-%d').date()
        slot.start_time = datetime.strptime(start_time_string, '%H:%M').time()
        slot.end_time = datetime.strptime(end_time_string, '%H:%M').time()
        slot.capacity = capacity

        db.session.commit()
        flash('Slot updated successfully!', 'success')
        return redirect(url_for('examiner.dashboard'))

    return render_template('examiner/edit_slot.html', slot=slot)


@examiner_bp.route('/slots/<int:slot_id>/delete', methods=['POST'])
@role_required('examiner')
def delete_slot(slot_id):
    examiner_id = session['user_id']
    slot = ExaminationSlot.query.get(slot_id)

    if slot.examiner_id != examiner_id:
        flash('You cannot delete slots created by other examiners.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    if slot.booked_count() > 0:
        flash('Students have already booked this slot. You cannot delete it.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    now = datetime.utcnow()
    if slot.examination.booking_start and now >= slot.examination.booking_start:
        flash('Student booking has started. You cannot delete this slot.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    db.session.delete(slot)
    db.session.commit()
    flash('Slot deleted successfully!', 'info')
    return redirect(url_for('examiner.dashboard'))


@examiner_bp.route('/slots/<int:slot_id>/students')
@role_required('examiner')
def view_slot_students(slot_id):
    examiner_id = session['user_id']
    slot = ExaminationSlot.query.get(slot_id)

    if slot.examiner_id != examiner_id:
        flash('You can only view students booked in your own slots.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    active_bookings = []
    for booking in slot.bookings:
        if booking.status != 'Cancelled':
            active_bookings.append(booking)

    return render_template('examiner/slot_students.html', slot=slot, bookings=active_bookings)


@examiner_bp.route('/bookings/<int:booking_id>/evaluate', methods=['GET', 'POST'])
@role_required('examiner')
def evaluate_student(booking_id):
    examiner_id = session['user_id']
    booking = Booking.query.get(booking_id)

    if booking.slot.examiner_id != examiner_id:
        flash('You are not authorized to evaluate this student.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    exam = booking.slot.examination
    rubrics = exam.rubrics

    if request.method == 'POST':
        total_score = 0
        remarks = request.form.get('remarks')

        for score in booking.evaluation_scores:
            db.session.delete(score)
        db.session.commit()

        for rubric in rubrics:
            marks_input = request.form.get('rubric_' + str(rubric.id))
            if marks_input:
                marks_val = int(marks_input)
            else:
                marks_val = 0

            if marks_val < 0 or marks_val > rubric.max_marks:
                flash('Marks must be between 0 and ' + str(rubric.max_marks), 'danger')
                return render_template('examiner/evaluate_student.html', booking=booking, rubrics=rubrics, existing_scores={})

            evaluation_score = EvaluationScore(
                booking_id=booking.id,
                rubric_id=rubric.id,
                marks_awarded=marks_val
            )
            db.session.add(evaluation_score)
            total_score = total_score + marks_val

        booking.total_marks_obtained = total_score
        booking.remarks = remarks
        booking.status = 'Completed'
        booking.evaluated_at = datetime.utcnow()

        db.session.commit()
        flash('Evaluation saved successfully!', 'success')
        return redirect(url_for('examiner.view_slot_students', slot_id=booking.slot_id))

    existing_scores = {}
    for score in booking.evaluation_scores:
        existing_scores[score.rubric_id] = score.marks_awarded

    return render_template(
        'examiner/evaluate_student.html',
        booking=booking,
        rubrics=rubrics,
        existing_scores=existing_scores
    )


@examiner_bp.route('/evaluations')
@role_required('examiner')
def evaluation_history():
    examiner_id = session['user_id']
    examiner = User.query.get(examiner_id)

    my_slots = ExaminationSlot.query.filter_by(examiner_id=examiner_id).all()
    slot_ids = []
    for s in my_slots:
        slot_ids.append(s.id)

    evaluated_bookings = []
    if slot_ids:
        all_bookings = Booking.query.filter_by(status='Completed').order_by(Booking.evaluated_at.desc()).all()
        for b in all_bookings:
            if b.slot_id in slot_ids:
                evaluated_bookings.append(b)

    return render_template(
        'examiner/evaluations.html',
        examiner=examiner,
        bookings=evaluated_bookings
    )

