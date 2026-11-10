from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    role = db.Column(db.String(20), nullable=False, default='student')
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    examiner_profile = db.relationship('ExaminerProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    slots_created = db.relationship('ExaminationSlot', backref='examiner', lazy=True)
    bookings = db.relationship('Booking', backref='student', lazy=True)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class ExaminerProfile(db.Model):
    __tablename__ = 'examiner_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=True)
    qualification = db.Column(db.String(100), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<ExaminerProfile user_id={self.user_id}>'


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    course_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    examinations = db.relationship('Examination', backref='course', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<Course {self.course_code}: {self.course_name}>'


class Examination(db.Model):
    __tablename__ = 'examinations'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    total_marks = db.Column(db.Integer, nullable=False, default=100)
    status = db.Column(db.String(30), nullable=False, default='Draft')

    slot_creation_start = db.Column(db.DateTime, nullable=True)
    slot_creation_end = db.Column(db.DateTime, nullable=True)
    booking_start = db.Column(db.DateTime, nullable=True)
    booking_end = db.Column(db.DateTime, nullable=True)
    exam_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rubrics = db.relationship('ExaminationRubric', backref='examination', cascade='all, delete-orphan', lazy=True)
    slots = db.relationship('ExaminationSlot', backref='examination', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<Examination "{self.title}" [{self.status}]>'


class ExaminationRubric(db.Model):
    __tablename__ = 'examination_rubrics'

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id'), nullable=False)
    criterion_name = db.Column(db.String(150), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Rubric "{self.criterion_name}" max={self.max_marks}>'


class ExaminationSlot(db.Model):
    __tablename__ = 'examination_slots'

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    slot_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=1)
    is_closed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='slot', cascade='all, delete-orphan', lazy=True)

    def booked_count(self):
        total_active_bookings = 0
        for booking in self.bookings:
            if booking.status != 'Cancelled':
                total_active_bookings += 1
        return total_active_bookings

    def is_available(self):
        if self.is_closed:
            return False
            
        if self.booked_count() < self.capacity:
            return True
        else:
            return False

    def __repr__(self):
        return f'<Slot {self.slot_date} {self.start_time}–{self.end_time}>'


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('examination_slots.id'), nullable=False)

    status = db.Column(db.String(20), nullable=False, default='Booked')
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_marks_obtained = db.Column(db.Integer, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    evaluated_at = db.Column(db.DateTime, nullable=True)

    evaluation_scores = db.relationship('EvaluationScore', backref='booking', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<Booking student={self.student_id} slot={self.slot_id} [{self.status}]>'


class EvaluationScore(db.Model):
    __tablename__ = 'evaluation_scores'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey('examination_rubrics.id'), nullable=False)
    marks_awarded = db.Column(db.Integer, nullable=False)

    rubric = db.relationship('ExaminationRubric')

    def __repr__(self):
        return f'<EvaluationScore rubric={self.rubric_id} marks={self.marks_awarded}>'