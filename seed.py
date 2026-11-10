from datetime import datetime, date, time, timedelta
from werkzeug.security import generate_password_hash
from app import app, db
from models import User, ExaminerProfile, Course, Examination, ExaminationRubric, ExaminationSlot, Booking

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(
            username='admin',
            email='admin@examportal.iitm.ac.in',
            full_name='System Administrator',
            password_hash=generate_password_hash('Admin@123'),
            role='admin',
            is_approved=True,
        )

        examiner1 = User(
            username='prof_sharma',
            email='sharma@iitm.ac.in',
            full_name='Prof. R. K. Sharma',
            password_hash=generate_password_hash('Examiner@123'),
            role='examiner',
            is_approved=True,
        )
        examiner1.examiner_profile = ExaminerProfile(
            department='Computer Science & Applications',
            qualification='Ph.D. in Software Engineering',
            bio='Interested in web frameworks, databases, and cloud systems.',
        )

        examiner2 = User(
            username='dr_anita',
            email='anita@iitm.ac.in',
            full_name='Dr. Anita Verma',
            password_hash=generate_password_hash('Examiner@123'),
            role='examiner',
            is_approved=False,
        )
        examiner2.examiner_profile = ExaminerProfile(
            department='Data Science',
            qualification='Ph.D. in Information Systems',
            bio='Works on data modelling, application development, and analytics.',
        )

        student = User(
            username='rahul_student',
            email='rahul@student.iitm.ac.in',
            full_name='Rahul Kumar',
            password_hash=generate_password_hash('Student@123'),
            role='student',
            is_approved=True,
        )

        course_mad = Course(
            course_code='CS2003',
            course_name='Modern Application Development I',
            description='Covers web development with Python, Flask, Jinja2, SQLite, and Bootstrap.',
        )
        course_dbms = Course(
            course_code='CS2001',
            course_name='Database Management Systems',
            description='Topics include relational algebra, SQL, normalisation, transactions, and indexing.',
        )

        db.session.add_all([admin, examiner1, examiner2, student, course_mad, course_dbms])
        db.session.commit()

        now = datetime.utcnow()
        exam = Examination(
            course_id=course_mad.id,
            title='MAD-I Term-End Viva & Project Evaluation',
            description='Oral viva on Flask architecture, SQLite models, routing, and Jinja2 templates.',
            total_marks=100,
            status='Slot Creation',
            slot_creation_start=now - timedelta(days=2),
            slot_creation_end=now + timedelta(days=5),
            booking_start=now + timedelta(days=6),
            booking_end=now + timedelta(days=12),
            exam_date=now + timedelta(days=15),
        )
        db.session.add(exam)
        db.session.commit()

        rubrics = [
            ExaminationRubric(
                examination_id=exam.id,
                criterion_name='Database Design & SQLAlchemy ORM',
                max_marks=30,
                description='Quality of ER modelling, correct use of relationships, and constraint definitions.',
            ),
            ExaminationRubric(
                examination_id=exam.id,
                criterion_name='Flask Routing & Controllers',
                max_marks=35,
                description='Clarity in route definitions, request handling, and form validation.',
            ),
            ExaminationRubric(
                examination_id=exam.id,
                criterion_name='Viva Q&A',
                max_marks=35,
                description='Ability to explain design decisions and answer questions confidently.',
            ),
        ]
        db.session.add_all(rubrics)

        slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=examiner1.id,
            slot_date=date.today() + timedelta(days=15),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity=3,
        )
        db.session.add(slot)
        db.session.commit()

        booking = Booking(
            student_id=student.id,
            slot_id=slot.id,
            status='Booked',
        )
        db.session.add(booking)
        db.session.commit()

        print('Database seeded successfully.\n')
        print('  admin          | Admin@123        (role: admin)')
        print('  prof_sharma    | Examiner@123     (role: examiner, approved)')
        print('  dr_anita       | Examiner@123     (role: examiner, pending approval)')
        print('  rahul_student  | Student@123      (role: student)')
        print(f'\n  Exam: "{exam.title}" with {len(rubrics)} rubrics and 1 slot.')

if __name__ == '__main__':
    seed()