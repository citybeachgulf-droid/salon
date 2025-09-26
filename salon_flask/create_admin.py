# create_admin.py
from app import create_app       # استدعاء دالة factory
from extensions import db
from models import User

def create_admin(username='admin', password='secret123'):
    app = create_app()           # إنشاء التطبيق
    with app.app_context():      # الدخول في context التطبيق
        user = User.query.filter_by(username=username).first()
        if user:
            print(f'User "{username}" exists. Updating password and role to admin.')
            user.set_password(password)
            user.role = 'admin'
        else:
            print(f'Creating new admin user "{username}"')
            user = User(username=username, role='admin')
            user.set_password(password)
            db.session.add(user)
        db.session.commit()
        print(f'Done. Admin user: {user.username}, role: {user.role}')

if __name__ == '__main__':
    create_admin()
