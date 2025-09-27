from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User, Employee
from extensions import db
from flask_jwt_extended import create_access_token
from flask import session  # مهم جدًا

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

            # توجيه حسب الصلاحية
            # توحيد الأسماء: اعتبر 'account_manager' نفس صلاحية 'accountant'
            role = 'accountant' if user.role in ['account_manager', 'accountant'] else user.role
            session['role'] = role

            # التأكد من وجود سجل Employee مرتبط بالمستخدم عند كون الدور موظف
            if role == 'staff':
                emp = Employee.query.filter_by(user_id=user.id).first()
                if not emp:
                    emp = Employee(name=user.username, user_id=user.id, role='staff')
                    db.session.add(emp)
                    db.session.commit()

            if role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            elif role == 'accountant':
                # صفحة المحاسبة هي الصفحة الرئيسية للمحاسب
                return redirect(url_for('main.accounting_dashboard'))
            else:
                return redirect(url_for('main.employee_bookings'))

        flash('Invalid credentials', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    # مسح بيانات الجلسة
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))