import os

curr_dir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'my-super-secret-key-123')
    
    db_path = os.path.join(curr_dir, 'instance', 'exam_portal.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')

    SQLALCHEMY_TRACK_MODIFICATIONS = False