from flask import Flask, redirect, url_for
from config import Config
from models import db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)

    with app.app_context():
        db.create_all()

    from auth import auth
    from admin import admin_bp
    from examiner import examiner_bp
    from student import student_bp

    app.register_blueprint(auth)
    app.register_blueprint(admin_bp)
    app.register_blueprint(examiner_bp)
    app.register_blueprint(student_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app