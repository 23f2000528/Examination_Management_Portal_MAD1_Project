from flask import Blueprint, render_template, session
from models import Booking
from utils import role_required

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@role_required('student')
def dashboard():
    student_id = session['user_id']
    my_bookings = (
        Booking.query
        .filter_by(student_id=student_id)
        .order_by(Booking.booked_at.desc())
        .all()
    )
    return render_template('student/dashboard.html', my_bookings=my_bookings)

