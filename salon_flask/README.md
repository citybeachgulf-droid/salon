Salon System - Flask + Bootstrap skeleton

How to run:

1. Create virtualenv:
   python -m venv venv
   venv\Scripts\activate   # on Windows
2. Install dependencies:
   pip install -r requirements.txt
3. Initialize DB:
   set FLASK_APP=app.py
   flask db init
   flask db migrate -m "initial"
   flask db upgrade
4. (Optional) create admin user via Python shell:
   from app import create_app
   from extensions import db
   from models import User
   app = create_app()
   with app.app_context():
       u = User(username='admin', email='admin@example.com')
       u.set_password('password')
       db.session.add(u); db.session.commit()

5. Run:
   python app.py

API:
  - /api/customers (GET, POST) - JWT required
  - Auth endpoints: /login, /register (form)
