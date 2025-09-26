# reset_db.py
from app import create_app
from extensions import db
from models import User

# إعداد التطبيق
app = create_app()

# بيانات الأدمن
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123"

with app.app_context():
    # حذف جميع الجداول
    db.drop_all()
    print("Dropped all tables.")

    # إنشاء جميع الجداول الجديدة
    db.create_all()
    print("Created all tables.")

    # إنشاء حساب الأدمن
    admin = User.query.filter_by(username=ADMIN_USERNAME).first()
    if admin:
        admin.set_password(ADMIN_PASSWORD)
        admin.role = "admin"
        print(f'Admin "{ADMIN_USERNAME}" exists. Password updated.')
    else:
        admin = User(username=ADMIN_USERNAME, role="admin")
        admin.set_password(ADMIN_PASSWORD)
        db.session.add(admin)
        print(f'Admin "{ADMIN_USERNAME}" created.')

    db.session.commit()
    print("Database reset completed successfully!")
