from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import Employee, User
from flask import session, redirect, url_for, flash
from models import Employee, User, Service, Booking, Supplier
from sqlalchemy import func
from datetime import datetime, date, timedelta
from models import Service, Employee, Customer, Sale, SaleItem,Inventory  
from models import Expense, Salary
from models import Revenue
from models import Inventory, InventoryTransaction, Employee
from decimal import Decimal
from werkzeug.utils import secure_filename
import os


pos_bp = Blueprint('pos', __name__, template_folder='../templates')

main_bp = Blueprint('main', __name__, template_folder='../templates')
UPLOAD_FOLDER = 'static/uploads/services'

from sqlalchemy import func
from models import Employee, Booking, Service

@main_bp.route('/')
def home():
    # واجهة العملاء هي الصفحة الرئيسية
    services = Service.query.all()
    employees = Employee.query.all()
    return render_template('customer_home.html', services=services, employees=employees)



@main_bp.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    # جلب كل الموظفين مع عدد الحجوزات والمجموع المكتسب
    employees = (
        db.session.query(
            Employee.id,
            Employee.name,
            Employee.specialty,
            func.count(Booking.id).label('bookings_count'),
            func.coalesce(func.sum(Service.price), 0).label('total_earned')
        )
        .outerjoin(Booking, Booking.employee_id == Employee.id)
        .outerjoin(Service, Service.id == Booking.service_id)
        .group_by(Employee.id)
        .all()
    )

    # جلب كل الخدمات
    services = Service.query.all()

    # جلب كل الموردين
    suppliers = Supplier.query.all()

    # المجاميع المالية العامة
    income_sum = db.session.query(func.coalesce(func.sum(Revenue.amount), 0)).scalar()
    expenses_sum = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar()
    salaries_sum = db.session.query(func.coalesce(func.sum(Salary.amount), 0)).scalar()

    # توحيد النوع إلى Decimal لتفادي أخطاء الجمع بين float و Decimal
    income_sum = income_sum if isinstance(income_sum, Decimal) else Decimal(str(income_sum or 0))
    expenses_sum = expenses_sum if isinstance(expenses_sum, Decimal) else Decimal(str(expenses_sum or 0))
    salaries_sum = salaries_sum if isinstance(salaries_sum, Decimal) else Decimal(str(salaries_sum or 0))

    total_income = income_sum
    total_expenses = expenses_sum + salaries_sum
    total_profit = total_income - total_expenses

    # عناصر المخزون منخفضة الكمية
    low_stock_items = Inventory.query.filter(Inventory.quantity <= Inventory.reorder_level).all()

    return render_template(
        'admin_dashboard.html',
        employees=employees,
        services=services,
        suppliers=suppliers,
        username=session.get('username'),
        total_income=total_income,
        total_expenses=total_expenses,
        total_profit=total_profit,
        low_stock_items=low_stock_items
    )





@main_bp.route('/add_supplier', methods=['POST'])
def add_supplier():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    name = request.form['name']
    phone = request.form.get('phone')
    notes = request.form.get('notes')
    amount_paid = request.form.get('amount_paid') or 0

    supplier = Supplier(name=name, phone=phone, notes=notes, amount_paid=amount_paid)
    db.session.add(supplier)
    db.session.commit()
    flash(f'Supplier {name} added successfully!', 'success')
    return redirect(url_for('main.admin_dashboard'))




@main_bp.route('/add_employee', methods=['POST'])
def add_employee():
    if session.get('role') != 'admin':
        return "Access Denied", 403
    
    name = request.form['name']
    role = request.form['role']  # هنا يمكن أن تكون account_manager
    password = request.form['password']

    # إنشاء مستخدم أولاً
    user = User(username=name.replace(" ","").lower(), role=role)
    user.set_password(password)
    db.session.add(user)

    # إضافة الموظف
    employee = Employee(name=name, specialty=request.form.get('specialty'), user=user)
    db.session.add(employee)

    db.session.commit()
    flash(f'تمت إضافة الموظف {name} بنجاح مع الصلاحية {role}!', 'success')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/services')
def admin_services():
    employees = Employee.query.all()
    services = Service.query.all()
    return render_template('admin_services.html', employees=employees, services=services)

@main_bp.route('/add_service', methods=['GET', 'POST'])
def add_service():
    if request.method == 'POST':
        service_name = request.form['service_name']
        service_price = float(request.form['service_price'])  # تأكد أنها float
        
        image_url = None
        if 'service_image' in request.files:
            file = request.files['service_image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                os.makedirs('static/uploads/services', exist_ok=True)  # تأكد من وجود المجلد
                file.save(os.path.join('static/uploads/services', filename))
                image_url = f'uploads/services/{filename}'
        
        # إضافة الخدمة لقاعدة البيانات
        new_service = Service(name=service_name, price=service_price, image_url=image_url)
        db.session.add(new_service)
        db.session.commit()
        
        flash(f'تمت إضافة الخدمة {service_name} بنجاح!', 'success')
        return redirect(url_for('main.admin_services'))  # إعادة التوجيه إلى صفحة عرض الخدمات
    
    return render_template('add_service.html')


@main_bp.route('/admin/services')
def services_list():
    services = Service.query.all()
    employees = Employee.query.all()
    return render_template('admin_services.html', services=services, employees=employees)



@main_bp.route('/pos')
def pos_dashboard():
    # السماح فقط للمحاسب أو المدير
    if session.get('role') not in ['admin', 'accountant']:
        return "Access Denied", 403

    # جلب جميع الموظفين (الذين يمكن استلام العملاء)
    employees = Employee.query.all()  # هنا بدل User.query
    customers = Customer.query.all()
    services = Service.query.all()
    
    return render_template(
        'pos_dashboard.html',
        employees=employees,
        customers=customers,
        services=services
    )











@main_bp.route('/suppliers', methods=['GET', 'POST'])
def suppliers_dashboard():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form.get('phone')
        notes = request.form.get('notes')
        paid_amount = request.form.get('paid_amount', 0)

        supplier = Supplier(
            name=name,
            phone=phone,
             notes=notes,
            amount_paid=paid_amount  # يمكن تعديل حسب حاجتك
        )
        db.session.add(supplier)
        db.session.commit()
        flash(f'تم إضافة المورد {name} بنجاح!', 'success')
        return redirect(url_for('main.suppliers_dashboard'))

    suppliers = Supplier.query.all()
    return render_template('suppliers_dashboard.html', suppliers=suppliers, username=session.get('username'))



@main_bp.route('/pay_supplier/<int:supplier_id>', methods=['POST'])
def pay_supplier(supplier_id):
    if session.get('role') != 'admin':
        return "Access Denied", 403

    supplier = Supplier.query.get_or_404(supplier_id)
    amount = Decimal(request.form.get('amount', '0'))  # تحويل إلى Decimal
    supplier.amount_paid += amount
    db.session.commit()
    flash(f'تم تسديد {amount} للمورد {supplier.name} بنجاح!', 'success')
    return redirect(url_for('main.suppliers_dashboard'))






# عرض المخزن وإضافة منتجات جديدة
@main_bp.route('/inventory', methods=['GET', 'POST'])
def inventory_dashboard():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    if request.method == 'POST':
        # إضافة منتج جديد
        product = request.form['product']
        quantity = int(request.form['quantity'])
        reorder_level = int(request.form['reorder_level'])

        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join('static/uploads/inventory', filename))
                image_url = url_for('static', filename=f'uploads/inventory/{filename}')

        new_item = Inventory(product=product, quantity=quantity, reorder_level=reorder_level, image_url=image_url)
        db.session.add(new_item)
        db.session.commit()
        flash('تم إضافة المنتج بنجاح!', 'success')
        return redirect(url_for('main.inventory_dashboard'))

    # عرض المنتجات الحالية
    items = Inventory.query.all()
    employees = Employee.query.all()
    return render_template('inventory.html', items=items, employees=employees)

# صرف المنتج للموظف
@main_bp.route('/inventory/assign', methods=['POST'])
def assign_inventory():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    inventory_id = request.form['inventory_id']
    employee_id = request.form['employee_id']
    quantity = int(request.form['quantity'])

    item = Inventory.query.get_or_404(inventory_id)
    if quantity > item.quantity:
        flash('الكمية المطلوبة أكبر من المخزون الحالي!', 'danger')
        return redirect(url_for('main.inventory_dashboard'))

    # تحديث المخزون
    item.quantity -= quantity
    transaction = InventoryTransaction(
        inventory_id=inventory_id,
        employee_id=employee_id,
        quantity=quantity
    )
    db.session.add(transaction)
    db.session.commit()
    flash(f'تم صرف {quantity} من {item.product} للموظف', 'success')
    return redirect(url_for('main.inventory_dashboard'))

@main_bp.route('/add_inventory', methods=['POST'])
def add_inventory():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    product = request.form['product']
    quantity = int(request.form['quantity'])
    reorder_level = int(request.form['reorder_level'])

    image_url = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join('static/uploads/inventory', filename))
            image_url = url_for('static', filename=f'uploads/inventory/{filename}')

    new_item = Inventory(product=product, quantity=quantity, reorder_level=reorder_level, image_url=image_url)
    db.session.add(new_item)
    db.session.commit()
    flash('تم إضافة المنتج بنجاح!', 'success')
    return redirect(url_for('main.inventory_dashboard'))



@main_bp.route('/employees')
def employees():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    employees = Employee.query.all()
    return render_template('employees.html', employees=employees)



@main_bp.route('/customers')
def customers():
    # صفحة العملاء للمدير فقط
    if session.get('role') != 'admin':
        return "Access Denied", 403

    customers = Customer.query.all()
    return render_template('customers.html', customers=customers)


@main_bp.route('/employees/<int:employee_id>')
def employee_detail(employee_id):
    # صفحة تفاصيل الموظف للمدير فقط
    if session.get('role') != 'admin':
        return "Access Denied", 403

    emp = Employee.query.get_or_404(employee_id)

    # قراءة شهر التصفية من الاستعلام (YYYY-MM)
    month_str = request.args.get('month')
    today = datetime.today().date()
    if month_str:
        try:
            year, month = map(int, month_str.split('-'))
            period_start = date(year, month, 1)
        except Exception:
            period_start = date(today.year, today.month, 1)
            month_str = period_start.strftime('%Y-%m')
    else:
        period_start = date(today.year, today.month, 1)
        month_str = period_start.strftime('%Y-%m')

    # حساب نهاية الفترة (أول يوم من الشهر التالي)
    if period_start.month == 12:
        period_end = date(period_start.year + 1, 1, 1)
    else:
        period_end = date(period_start.year, period_start.month + 1, 1)

    # تاريخ بدء العمل (تخمين): أقدم تاريخ نشاط مسجل (حجز/بيع/صرف مخزون)
    earliest_booking = db.session.query(func.min(Booking.date)).filter(Booking.employee_id == emp.id).scalar()
    earliest_sale_dt = db.session.query(func.min(Sale.date)).filter(Sale.employee_id == emp.id).scalar()
    earliest_txn_dt = db.session.query(func.min(InventoryTransaction.date)).filter(InventoryTransaction.employee_id == emp.id).scalar()

    candidates = []
    if earliest_booking:
        candidates.append(earliest_booking if isinstance(earliest_booking, date) else earliest_booking)
    if earliest_sale_dt:
        candidates.append(earliest_sale_dt.date() if hasattr(earliest_sale_dt, 'date') else earliest_sale_dt)
    if earliest_txn_dt:
        candidates.append(earliest_txn_dt.date() if hasattr(earliest_txn_dt, 'date') else earliest_txn_dt)

    start_work_date = None
    if candidates:
        start_work_date = min(candidates)

    # إجمالي الدخل لهذا الشهر (من الحجوزات المكتملة)
    income_total = (
        db.session.query(func.coalesce(func.sum(Service.price), 0))
        .select_from(Booking)
        .join(Service, Service.id == Booking.service_id)
        .filter(
            Booking.employee_id == emp.id,
            Booking.date >= period_start,
            Booking.date < period_end,
            Booking.status == 'completed'
        )
        .scalar()
    )

    # عدد الحجوزات المكتملة هذا الشهر
    bookings_count = (
        db.session.query(func.count(Booking.id))
        .filter(
            Booking.employee_id == emp.id,
            Booking.date >= period_start,
            Booking.date < period_end,
            Booking.status == 'completed'
        )
        .scalar()
    )

    # تفصيل الدخل لكل خدمة خلال الشهر
    services_breakdown = (
        db.session.query(
            Service.name,
            func.count(Booking.id).label('count'),
            func.coalesce(func.sum(Service.price), 0).label('total')
        )
        .select_from(Booking)
        .join(Service, Service.id == Booking.service_id)
        .filter(
            Booking.employee_id == emp.id,
            Booking.date >= period_start,
            Booking.date < period_end,
            Booking.status == 'completed'
        )
        .group_by(Service.id)
        .all()
    )

    # استهلاك المنتجات خلال الشهر
    usage_rows = (
        db.session.query(
            Inventory.product,
            func.coalesce(func.sum(InventoryTransaction.quantity), 0).label('qty')
        )
        .select_from(InventoryTransaction)
        .join(Inventory, Inventory.id == InventoryTransaction.inventory_id)
        .filter(
            InventoryTransaction.employee_id == emp.id,
            InventoryTransaction.date >= period_start,
            InventoryTransaction.date < period_end
        )
        .group_by(Inventory.product)
        .all()
    )

    total_products_used = sum(row.qty for row in usage_rows) if usage_rows else 0

    return render_template(
        'employee_detail.html',
        employee=emp,
        month_str=month_str,
        period_start=period_start,
        income_total=income_total,
        bookings_count=bookings_count,
        services_breakdown=services_breakdown,
        usage_rows=usage_rows,
        total_products_used=total_products_used,
        start_work_date=start_work_date
    )

@main_bp.route('/delete_employee/<int:employee_id>', methods=['POST'])
def delete_employee(employee_id):
    if session.get('role') != 'admin':
        return "Access Denied", 403
    emp = Employee.query.get_or_404(employee_id)
    # حذف المستخدم المرتبط إذا موجود
    user = User.query.filter_by(username=emp.name.replace(" ","").lower()).first()
    if user:
        db.session.delete(user)
    db.session.delete(emp)
    db.session.commit()
    flash(f'تم حذف الموظف {emp.name}', 'success')
    return redirect(url_for('main.employees'))






@main_bp.route('/accounting_dashboard')
def accounting_dashboard():
    if session.get('role') not in ['admin', 'accountant']:
        return "Access Denied", 403
    # المجاميع
    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar()
    total_salaries = db.session.query(func.coalesce(func.sum(Salary.amount), 0)).scalar()
    total_revenue = db.session.query(func.coalesce(func.sum(Revenue.amount), 0)).scalar()

    employees = Employee.query.all()

    # دمج المصاريف والرواتب لعرضها في جدول واحد
    expense_records = Expense.query.order_by(Expense.date.desc()).all()
    salary_records = Salary.query.order_by(Salary.date.desc()).all()

    records = []
    for e in expense_records:
        e.type = 'expense'
        records.append(e)
    for s in salary_records:
        s.type = 'salary'
        records.append(s)

    # ترتيب حسب التاريخ الموحد بالحقل "date"
    records.sort(key=lambda x: x.date, reverse=True)

    # الإيرادات للعرض
    revenues = Revenue.query.order_by(Revenue.date.desc()).all()

    return render_template(
        'accounting_dashboard.html',
        total_expenses=total_expenses,
        total_salaries=total_salaries,
        total_revenue=total_revenue,
        employees=employees,
        records=records,
        revenues=revenues
    )

@main_bp.route('/add_expense', methods=['POST'])
def add_expense():
    if session.get('role') != 'accountant':
        return "Access Denied", 403

    description = request.form['description']
    amount = float(request.form['amount'])
    expense = Expense(description=description, amount=amount)
    db.session.add(expense)
    db.session.commit()
    flash('تمت إضافة المصروف بنجاح', 'success')
    return redirect(url_for('main.accounting_dashboard'))

@main_bp.route('/add_salary', methods=['POST'])
def add_salary():
    if session.get('role') != 'accountant':
        return "Access Denied", 403

    employee_name = request.form['employee_name']
    month = request.form['month']
    amount = float(request.form['amount'])
    salary = Salary(employee_name=employee_name, amount=amount, month=month)
    db.session.add(salary)
    db.session.commit()
    flash('تمت إضافة الراتب بنجاح', 'success')
    return redirect(url_for('main.accounting_dashboard'))





@main_bp.route('/create_booking', methods=['POST'])
def create_booking():
    # السماح فقط للمحاسب أو المدير
    if session.get('role') not in ['accountant', 'admin']:
        return "Access Denied", 403

    service_id = request.form['service_id']
    employee_id = request.form['employee_id']
    customer_name = request.form['customer_name']
    customer_phone = request.form['customer_phone']

    # إنشاء العميل أولاً إذا لم يكن موجود
    customer = Customer.query.filter_by(phone=customer_phone).first()
    if not customer:
        customer = Customer(name=customer_name, phone=customer_phone)
        db.session.add(customer)
        db.session.commit()

    # التأكد من أن الموظف موجود
    employee = Employee.query.get(employee_id)
    if not employee:
        flash("الموظف المحدد غير موجود!", "danger")
        return redirect(url_for('main.pos_dashboard'))

    # إنشاء الحجز
    booking = Booking(
        customer_id=customer.id,
        service_id=service_id,
        employee_id=employee.id,
        date=datetime.today(),
        time=datetime.now().time(),
        status='booked'
    )
    db.session.add(booking)
    db.session.commit()

    flash("تم تسجيل الخدمة بنجاح للعميل والموظف المحدد", "success")
    return redirect(url_for('main.pos_dashboard'))


@main_bp.route('/inventory/issue', methods=['POST'])
def issue_inventory():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    inventory_id = request.form['inventory_id']
    employee_id = request.form['employee_id']
    quantity = int(request.form['quantity'])

    item = Inventory.query.get_or_404(inventory_id)

    if quantity > item.quantity:
        flash("الكمية المطلوبة أكبر من المخزون الحالي!", "danger")
        return redirect(url_for('main.inventory_dashboard'))

    # تسجيل العملية
    transaction = InventoryTransaction(
        inventory_id=inventory_id,
        employee_id=employee_id,
        quantity=quantity
    )
    db.session.add(transaction)

    # تحديث المخزون
    item.quantity -= quantity
    db.session.commit()

    flash(f"تم صرف {quantity} من {item.product} للموظف.", "success")
    return redirect(url_for('main.inventory_dashboard'))




@main_bp.route('/employee/bookings')
def employee_bookings():
    if session.get('role') != 'staff':
        return "Access Denied", 403

    # جلب الموظف الحالي
    employee = (
        db.session.query(Employee)
        .join(User, Employee.user_id == User.id)
        .filter(User.username == session.get('username'))
        .first()
    )
    if not employee:
        return "Employee not found", 404

    # جلب جميع الحجوزات الخاصة بهذا الموظف
    bookings = Booking.query.filter_by(employee_id=employee.id).all()

    return render_template('employee_bookings.html', bookings=bookings)


# صفحة استهلاك المخزن للموظف
@main_bp.route('/employee/inventory', methods=['GET'])
def employee_inventory():
    if session.get('role') != 'staff':
        return "Access Denied", 403

    employee = (
        db.session.query(Employee)
        .join(User, Employee.user_id == User.id)
        .filter(User.username == session.get('username'))
        .first()
    )
    if not employee:
        return "Employee not found", 404

    items = Inventory.query.all()
    # آخر الحركات الخاصة بالموظف
    recent_txns = (
        db.session.query(InventoryTransaction)
        .filter(InventoryTransaction.employee_id == employee.id)
        .order_by(InventoryTransaction.date.desc())
        .limit(20)
        .all()
    )
    return render_template('employee_inventory.html', items=items, employee=employee, recent_txns=recent_txns)


@main_bp.route('/employee/inventory/consume', methods=['POST'])
def employee_consume_inventory():
    if session.get('role') != 'staff':
        return "Access Denied", 403

    employee = (
        db.session.query(Employee)
        .join(User, Employee.user_id == User.id)
        .filter(User.username == session.get('username'))
        .first()
    )
    if not employee:
        return "Employee not found", 404

    inventory_id = request.form.get('inventory_id')
    quantity_str = request.form.get('quantity', '1')
    try:
        quantity = int(quantity_str)
    except Exception:
        quantity = 1
    if quantity <= 0:
        quantity = 1

    item = Inventory.query.get_or_404(inventory_id)
    if quantity > item.quantity:
        flash('الكمية المطلوبة أكبر من المخزون الحالي!', 'danger')
        return redirect(url_for('main.employee_inventory'))

    # تسجيل الحركة وتحديث المخزون
    txn = InventoryTransaction(inventory_id=item.id, employee_id=employee.id, quantity=quantity)
    db.session.add(txn)
    item.quantity -= quantity
    db.session.commit()

    flash(f'تم تسجيل استهلاك {quantity} من {item.product}', 'success')
    return redirect(url_for('main.employee_inventory'))




@main_bp.route('/update_booking_status/<int:booking_id>', methods=['POST'])
def update_booking_status(booking_id):
    if session.get('role') != 'staff':
        return "Access Denied", 403

    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    old_status = booking.status
    booking.status = new_status

    # تسجيل دخل عند اكتمال الحجز لأول مرة
    if new_status == 'completed' and old_status != 'completed':
        service = Service.query.get(booking.service_id)
        if service:
            rev_date = booking.date if isinstance(booking.date, date) else datetime.utcnow().date()
            revenue = Revenue(
                source=f"Booking - {service.name}",
                amount=service.price,
                date=rev_date
            )
            db.session.add(revenue)

    db.session.commit()
    flash(f'تم تحديث حالة الحجز إلى {new_status}', 'success')
    return redirect(url_for('main.employee_bookings'))



@main_bp.route('/pos/bookings', methods=['GET', 'POST'])
def pos_bookings():
    """
    صفحة إدارة الحجوزات لمنفذ المبيعات أو المدير.
    GET: عرض قائمة الحجوزات ونماذج الإدخال.
    POST: تسجيل حجز جديد.
    """
    # السماح لمنفذ المبيعات، المدير، والموظفين بالوصول للعرض
    if session.get('role') not in ['accountant', 'admin', 'staff']:
        return "Access Denied", 403

    # جلب جميع الموظفين والخدمات والعملاء والحجوزات
    employees = Employee.query.all()
    services = Service.query.all()
    customers = Customer.query.all()
    bookings = Booking.query.order_by(Booking.date.desc(), Booking.time.desc()).all()

    if request.method == 'POST':
        # تقييد إنشاء الحجوزات على المحاسب أو المدير فقط
        if session.get('role') not in ['accountant', 'admin']:
            return "Access Denied", 403
        # جمع بيانات الحجز من الفورم
        customer_name = request.form.get('customer_name')
        customer_phone = request.form.get('customer_phone')
        service_id = request.form.get('service_id')
        employee_id = request.form.get('employee_id')
        booking_date = request.form.get('booking_date')
        booking_time = request.form.get('booking_time')

        # تحقق إذا العميل موجود مسبقًا
        customer = Customer.query.filter_by(phone=customer_phone).first()
        if not customer:
            customer = Customer(name=customer_name, phone=customer_phone)
            db.session.add(customer)
            db.session.commit()

        # التأكد من أن الموظف موجود
        employee = Employee.query.get(employee_id)
        if not employee:
            flash("الموظف المحدد غير موجود!", "danger")
            return redirect(url_for('main.pos_bookings'))

        # إنشاء الحجز
        booking = Booking(
            customer_id=customer.id,
            service_id=service_id,
            employee_id=employee.id,
            date=datetime.strptime(booking_date, '%Y-%m-%d'),
            time=datetime.strptime(booking_time, '%H:%M').time(),
            status='booked'
        )
        db.session.add(booking)
        db.session.commit()

        flash("تم تسجيل الحجز بنجاح!", "success")
        return redirect(url_for('main.pos_bookings'))

    # تمرير جميع البيانات للقالب
    return render_template(
        'pos_bookings.html',
        employees=employees,
        services=services,
        customers=customers,
        bookings=bookings
    )




@main_bp.route('/customer/bookings', methods=['GET', 'POST'])
def customer_booking_page():
    services = Service.query.all()
    employees = Employee.query.all()

    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        customer_phone = request.form.get('customer_phone')
        service_id = request.form.get('service_id')
        employee_id = request.form.get('employee_id')
        booking_date = request.form.get('booking_date')
        booking_time = request.form.get('booking_time')

        # التأكد من وجود العميل
        customer = Customer.query.filter_by(phone=customer_phone).first()
        if not customer:
            customer = Customer(name=customer_name, phone=customer_phone)
            db.session.add(customer)
            db.session.commit()

        # التأكد من وجود الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            flash("الموظف المختار غير موجود!", "danger")
            return redirect(url_for('main.customer_booking_page'))

        # إنشاء الحجز
        booking = Booking(
            customer_id=customer.id,
            service_id=service_id,
            employee_id=employee.id,
            date=datetime.strptime(booking_date, '%Y-%m-%d'),
            time=datetime.strptime(booking_time, '%H:%M').time(),
            status='booked'
        )
        db.session.add(booking)
        db.session.commit()
        flash("تم تسجيل الحجز بنجاح!", "success")
        return redirect(url_for('main.customer_booking_page'))

    return render_template('customer_booking.html', services=services, employees=employees)



@main_bp.route('/api/available_times')
def available_times():
    service_id = request.args.get('service_id')
    date_str = request.args.get('date')
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

    # جميع الأوقات الممكنة (مثال: 9 ص - 5 م كل نصف ساعة)
    all_times = [f"{h:02d}:{m:02d}" for h in range(9, 18) for m in (0,30)]

    # حذف الأوقات المحجوزة مسبقًا
    booked = Booking.query.filter_by(service_id=service_id, date=date_obj).all()
    booked_times = [b.time.strftime("%H:%M") for b in booked]
    available = [t for t in all_times if t not in booked_times]

    return {'times': available}


# -----------------------------
# POS: Create Sale and Invoice
# -----------------------------
@main_bp.route('/pos/sales/create', methods=['POST'])
def create_sale():
    # السماح فقط للمحاسب أو المدير
    if session.get('role') not in ['accountant', 'admin']:
        return "Access Denied", 403

    service_id = request.form.get('service_id')
    employee_id = request.form.get('employee_id')
    customer_name = request.form.get('customer_name')
    customer_phone = request.form.get('customer_phone')
    quantity_str = request.form.get('quantity', '1')

    try:
        quantity = int(quantity_str)
        if quantity <= 0:
            quantity = 1
    except Exception:
        quantity = 1

    # التأكد من وجود الخدمة والموظف
    service = Service.query.get(service_id)
    if not service:
        flash("الخدمة غير موجودة!", "danger")
        return redirect(url_for('main.pos_dashboard'))

    employee = Employee.query.get(employee_id)
    if not employee:
        flash("الموظف المحدد غير موجود!", "danger")
        return redirect(url_for('main.pos_dashboard'))

    # إنشاء العميل إذا لزم
    customer = None
    if customer_phone:
        customer = Customer.query.filter_by(phone=customer_phone).first()
    if not customer and customer_name and customer_phone:
        customer = Customer(name=customer_name, phone=customer_phone)
        db.session.add(customer)
        db.session.commit()

    # حساب المجموع وإنشاء البيع
    unit_price = Decimal(str(service.price))
    total_amount = unit_price * quantity

    sale = Sale(
        employee_id=employee.id,
        customer_id=customer.id if customer else None,
        total_amount=total_amount,
        date=datetime.utcnow()
    )
    db.session.add(sale)
    db.session.flush()  # للحصول على sale.id قبل الالتزام

    sale_item = SaleItem(
        sale_id=sale.id,
        service_id=service.id,
        quantity=quantity,
        price=unit_price
    )
    db.session.add(sale_item)
    # سجل الدخل مباشرة عند إنشاء عملية بيع
    revenue = Revenue(
        source=f"POS - {service.name}",
        amount=total_amount,
        date=datetime.utcnow().date()
    )
    db.session.add(revenue)
    db.session.commit()

    # توجيه إلى صفحة الفاتورة
    return redirect(url_for('main.view_invoice', sale_id=sale.id))


@main_bp.route('/pos/invoice/<int:sale_id>')
def view_invoice(sale_id):
    # السماح فقط للمحاسب أو المدير
    if session.get('role') not in ['accountant', 'admin']:
        return "Access Denied", 403

    sale = Sale.query.get_or_404(sale_id)
    return render_template('invoice.html', sale=sale)
