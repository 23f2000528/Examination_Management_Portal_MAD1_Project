from datetime import datetime, date, time
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from models import (
    db, User, ExaminerProfile, Course, Examination,
    ExaminationRubric, ExaminationSlot, Booking, EvaluationScore
)
from utils import role_required

examiner_bp = Blueprint('examiner', __name__, url_prefix='/examiner')

#Examiner Dashboard
@examiner_bp.route('/dashboard')
@role_required('examiner')
def dashboard():
    examiner_id = session['user_id']
    examiner = User.query.get_or_404(examiner_id)

    #Exam open for slots 
    active_exams = Examination.query.filter(
        Examination.status.in_(['Slot Creation', 'Booking Open', 'Closed'])
    ).all()

   #Examiner Slot creation
    my_slots = ExaminationSlot.query.filter_by(examiner_id=examiner_id).order_by(
        ExaminationSlot.slot_date.desc(), ExaminationSlot.start_time.asc()
    ).all()

    #Total students booked in this examiner's slots
    all_bookings = []
    for s in my_slots:
        all_bookings.extend([b for b in s.bookings if b.status != 'Cancelled'])

    total_booked = len(all_bookings)
    pending_evaluations = len([b for b in all_bookings if b.status == 'Booked' and b.total_marks_obtained is None])
    completed_evaluations = len([b for b in all_bookings if b.status == 'Completed'])

    return render_template(
        'examiner/dashboard.html',
        examiner=examiner,
        active_exams=active_exams,
        my_slots=my_slots,
        total_booked=total_booked,
        pending_evaluations=pending_evaluations,
        completed_evaluations=completed_evaluations
    )


#profile manage
@examiner_bp.route('/profile', methods=['GET', 'POST'])
@role_required('examiner')
def profile():
    examiner_id = session['user_id']
    user = User.query.get_or_404(examiner_id)

    #profile existing or not
    if not user.examiner_profile:
        user.examiner_profile = ExaminerProfile(user_id=user.id)
        db.session.commit()

    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '').strip()
        user.examiner_profile.department = request.form.get('department', '').strip() or None
        user.examiner_profile.qualification = request.form.get('qualification', '').strip() or None
        user.examiner_profile.bio = request.form.get('bio', '').strip() or None

        db.session.commit()
        session['user_name'] = user.full_name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('examiner.dashboard'))

    return render_template('examiner/profile.html', user=user)

#examiner slot creation
@examiner_bp.route('/slots/create', methods=['GET', 'POST'])
@role_required('examiner')
def create_slot():
    examiner_id = session['user_id']
    now = datetime.utcnow()

    available_exams = Examination.query.filter(
        Examination.status.in_(['Slot Creation', 'Draft'])
    ).all()

    # Filter strictly according to timeline windows if defined
    eligible_exams = []
    for exam in available_exams:
        if exam.status == 'Slot Creation':
            start_ok = (exam.slot_creation_start is None) or (now >= exam.slot_creation_start)
            end_ok = (exam.slot_creation_end is None) or (now <= exam.slot_creation_end)
            if start_ok and end_ok:
                eligible_exams.append(exam)
        elif exam.status == 'Draft':
            # Allow examiners to prepare if admin enabled slot creation start
            if exam.slot_creation_start and exam.slot_creation_end:
                if exam.slot_creation_start <= now <= exam.slot_creation_end:
                    eligible_exams.append(exam)

    if request.method == 'POST':
        exam_id = request.form.get('examination_id', type=int)
        slot_date_str = request.form.get('slot_date')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        capacity = request.form.get('capacity', type=int) or 1

        exam = Examination.query.get_or_404(exam_id)

        if exam.slot_creation_start and now < exam.slot_creation_start:
            flash(f'Slot creation has not started yet for "{exam.title}". Opens on {exam.slot_creation_start.strftime("%d %b %Y, %H:%M")}.', 'danger')
            return redirect(url_for('examiner.create_slot'))

        if exam.slot_creation_end and now > exam.slot_creation_end:
            flash(f'Slot creation window for "{exam.title}" closed on {exam.slot_creation_end.strftime("%d %b %Y, %H:%M")}.', 'danger')
            return redirect(url_for('examiner.create_slot'))

        try:
            slot_date = datetime.strptime(slot_date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except (ValueError, TypeError):
            flash('Invalid date or time format provided.', 'danger')
            return render_template('examiner/create_slot.html', eligible_exams=eligible_exams)

        if start_time >= end_time:
            flash('Slot start time must be earlier than end time.', 'danger')
            return render_template('examiner/create_slot.html', eligible_exams=eligible_exams)

        if capacity < 1:
            flash('Slot capacity must be at least 1 student.', 'danger')
            return render_template('examiner/create_slot.html', eligible_exams=eligible_exams)

        new_slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=examiner_id,
            slot_date=slot_date,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            is_closed=False
        )
        db.session.add(new_slot)
        db.session.commit()

        flash(f'Examination slot on {slot_date.strftime("%d %b %Y")} ({start_time_str} - {end_time_str}) created successfully!', 'success')
        return redirect(url_for('examiner.dashboard'))

    return render_template('examiner/create_slot.html', eligible_exams=eligible_exams)

#exam slot editing
@examiner_bp.route('/slots/<int:slot_id>/edit', methods=['GET', 'POST'])
@role_required('examiner')
def edit_slot(slot_id):
    examiner_id = session['user_id']
    slot = ExaminationSlot.query.get_or_404(slot_id)

    if slot.examiner_id != examiner_id:
        flash('Unauthorized: You can only edit slots created by you.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    if slot.booked_count() > 0:
        flash('Cannot edit slot: Students have already booked this slot.', 'warning')
        return redirect(url_for('examiner.dashboard'))

    now = datetime.utcnow()
    exam = slot.examination
    if exam.booking_start and now >= exam.booking_start:
        flash(f'Cannot edit slot: Student booking period has already commenced for {exam.title}.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    if request.method == 'POST':
        slot_date_str = request.form.get('slot_date')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        capacity = request.form.get('capacity', type=int) or 1

        try:
            slot.slot_date = datetime.strptime(slot_date_str, '%Y-%m-%d').date()
            slot.start_time = datetime.strptime(start_time_str, '%H:%M').time()
            slot.end_time = datetime.strptime(end_time_str, '%H:%M').time()
            slot.capacity = capacity
            db.session.commit()
            flash('Slot details updated successfully!', 'success')
            return redirect(url_for('examiner.dashboard'))
        except (ValueError, TypeError):
            flash('Invalid date or time values.', 'danger')

    return render_template('examiner/edit_slot.html', slot=slot)


@examiner_bp.route('/slots/<int:slot_id>/delete', methods=['POST'])
@role_required('examiner')
def delete_slot(slot_id):
    examiner_id = session['user_id']
    slot = ExaminationSlot.query.get_or_404(slot_id)

    if slot.examiner_id != examiner_id:
        flash('Unauthorized: You can only delete your own slots.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    if slot.booked_count() > 0:
        flash('Cannot delete slot: Students are already booked for this session.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    now = datetime.utcnow()
    if slot.examination.booking_start and now >= slot.examination.booking_start:
        flash('Cannot delete slot: Student booking period is already active.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    db.session.delete(slot)
    db.session.commit()
    flash('Examination slot removed successfully.', 'info')
    return redirect(url_for('examiner.dashboard'))

#view booked candidates and evaluation 
@examiner_bp.route('/slots/<int:slot_id>/students')
@role_required('examiner')
def view_slot_students(slot_id):
    examiner_id = session['user_id']
    slot = ExaminationSlot.query.get_or_404(slot_id)

    #authoritization check
    if slot.examiner_id != examiner_id:
        flash('Unauthorized: You can only view candidates booked into your own slots.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    active_bookings = [b for b in slot.bookings if b.status != 'Cancelled']
    return render_template('examiner/slot_students.html', slot=slot, bookings=active_bookings)


@examiner_bp.route('/bookings/<int:booking_id>/evaluate', methods=['GET', 'POST'])
@role_required('examiner')
def evaluate_student(booking_id):
    examiner_id = session['user_id']
    booking = Booking.query.get_or_404(booking_id)

    #examiner authorize check
    if booking.slot.examiner_id != examiner_id:
        flash('Unauthorized: You are not authorized to evaluate this candidate.', 'danger')
        return redirect(url_for('examiner.dashboard'))

    exam = booking.slot.examination
    rubrics = exam.rubrics

    if not rubrics:
        flash('No rubrics defined for this examination yet. Contact Admin to set up rubrics.', 'warning')

    if request.method == 'POST':
        total_score = 0
        remarks = request.form.get('remarks', '').strip()

        #clear partial score
        EvaluationScore.query.filter_by(booking_id=booking.id).delete()

        #collect score per rubrics
        for rubric in rubrics:
            field_name = f'rubric_{rubric.id}'
            score_val = request.form.get(field_name, type=int) or 0

           #validate score within bound
            if score_val < 0 or score_val > rubric.max_marks:
                flash(f'Marks for "{rubric.criterion_name}" must be between 0 and {rubric.max_marks}.', 'danger')
                return render_template('examiner/evaluate_student.html', booking=booking, rubrics=rubrics)

            eval_score = EvaluationScore(
                booking_id=booking.id,
                rubric_id=rubric.id,
                marks_awarded=score_val
            )
            db.session.add(eval_score)
            total_score += score_val

        #finialising booking record
        booking.total_marks_obtained = total_score
        booking.remarks = remarks
        booking.status = 'Completed'
        booking.evaluated_at = datetime.utcnow()

        db.session.commit()
        flash(f'Evaluation submitted successfully for {booking.student.full_name}! Total Score: {total_score}/{exam.total_marks}', 'success')
        return redirect(url_for('examiner.view_slot_students', slot_id=booking.slot_id))

    #existing record re evaluate
    existing_scores = {es.rubric_id: es.marks_awarded for es in booking.evaluation_scores}

    return render_template(
        'examiner/evaluate_student.html',
        booking=booking,
        rubrics=rubrics,
        existing_scores=existing_scores
    )
