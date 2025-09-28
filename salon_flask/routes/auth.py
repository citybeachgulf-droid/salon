from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User, Employee
from extensions import db

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # حفظ البيانات في session
            session['username'] = user.username
            session['role'] = user.role
            session['user_id'] = user.id

            role = user.role  # خذ الدور كما هو بدون توحيد
            session['role'] = role

            # توجيه حسب الصلاحية
            if role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            elif role == 'account_manager':
                return redirect(url_for('main.account_manager_dashboard'))
            elif role == 'accountant':
                # فقط الوصول لمنفذ البيع
                return redirect(url_for('main.pos_dashboard'))
            elif role == 'staff':
                # التأكد من وجود سجل Employee مرتبط بالمستخدم
                emp = Employee.query.filter_by(user_id=user.id).first()
                if not emp:
                    emp = Employee(name=user.username, user_id=user.id, role='staff')
                    db.session.add(emp)
                    db.session.commit()
                return redirect(url_for('main.employee_bookings'))
            else:
                flash('Role not recognized', 'danger')
                return redirect(url_for('auth.login'))

        flash('Invalid credentials', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    # مسح بيانات الجلسة
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))
