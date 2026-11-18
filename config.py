import os

curr_dir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(curr_dir, 'instance')
os.makedirs(instance_dir, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'my-super-secret-key-123')
    
    db_path = os.path.join(instance_dir, 'exam_portal.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
