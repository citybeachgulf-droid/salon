from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import Employee, User
from flask import session, redirect, url_for, flash
from models import Employee, User, Service, Booking, Supplier, Offer
from sqlalchemy import func
from datetime import datetime, date, timedelta
from models import Service, Employee, Customer, Sale, SaleItem,Inventory  
from models import Expense, Salary
from models import Revenue
from models import Inventory, InventoryTransaction, Employee
from models import Payment
from decimal import Decimal
from werkzeug.utils import secure_filename
import os
import uuid
import json
from sqlalchemy import and_


pos_bp = Blueprint('pos', __name__, template_folder='../templates')

main_bp = Blueprint('main', __name__, template_folder='../templates')
UPLOAD_FOLDER = 'static/uploads/services'
OFFERS_UPLOAD_FOLDER = 'static/uploads/offers'

from sqlalchemy import func
from models import Employee, Booking, Service

@main_bp.route('/')
def home():
    # واجهة العملاء هي الصفحة الرئيسية
    services = Service.query.all()
    employees = Employee.query.all()
    categories = _load_gallery_categories()
    offers = Offer.query.filter_by(active=True).order_by(Offer.sort_order.asc(), Offer.created_at.desc()).all()
    return render_template('customer_home.html', services=services, employees=employees, categories=categories, offers=offers)



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
    employee = Employee(name=name, specialty=request.form.get('specialty'), role=role, user=user)
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


# -----------------------------
# Admin: Offers CRUD
# -----------------------------
@main_bp.route('/admin/offers', methods=['GET', 'POST'])
def admin_offers():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    os.makedirs(OFFERS_UPLOAD_FOLDER, exist_ok=True)

    if request.method == 'POST':
        action = (request.form.get('action') or 'create').strip()

        if action == 'create':
            title = (request.form.get('title') or '').strip()
            description = (request.form.get('description') or '').strip() or None
            price_str = (request.form.get('price') or '').strip()
            active_val = request.form.get('active')
            sort_order_str = (request.form.get('sort_order') or '0').strip()
            image_file = request.files.get('image')

            if not title:
                flash('العنوان مطلوب.', 'danger')
                return redirect(url_for('main.admin_offers'))

            image_url = None
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                save_path = os.path.join(OFFERS_UPLOAD_FOLDER, unique_name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                image_file.save(save_path)
                image_url = f"uploads/offers/{unique_name}"

            try:
                price = Decimal(str(price_str)) if price_str else None
            except Exception:
                price = None
            try:
                sort_order = int(sort_order_str)
            except Exception:
                sort_order = 0
            is_active = True if (active_val and str(active_val).lower() in ['1','true','yes','on']) else False

            offer = Offer(title=title, description=description, price=price, image_url=image_url, active=is_active, sort_order=sort_order)
            db.session.add(offer)
            db.session.commit()
            flash('تم إنشاء العرض بنجاح.', 'success')
            return redirect(url_for('main.admin_offers'))

        if action == 'update':
            offer_id = request.form.get('id')
            offer = Offer.query.get_or_404(offer_id)
            offer.title = (request.form.get('title') or offer.title).strip()
            offer.description = (request.form.get('description') or '').strip() or None
            price_str = (request.form.get('price') or '').strip()
            try:
                offer.price = Decimal(str(price_str)) if price_str else None
            except Exception:
                pass
            sort_order_str = (request.form.get('sort_order') or '').strip()
            try:
                offer.sort_order = int(sort_order_str) if sort_order_str else offer.sort_order
            except Exception:
                pass
            active_val = request.form.get('active')
            if active_val is not None:
                offer.active = True if str(active_val).lower() in ['1','true','yes','on'] else False

            image_file = request.files.get('image')
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                save_path = os.path.join(OFFERS_UPLOAD_FOLDER, unique_name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                image_file.save(save_path)
                offer.image_url = f"uploads/offers/{unique_name}"

            db.session.commit()
            flash('تم تحديث العرض.', 'success')
            return redirect(url_for('main.admin_offers'))

    offers = Offer.query.order_by(Offer.sort_order.asc(), Offer.created_at.desc()).all()
    return render_template('admin_offers.html', offers=offers)


@main_bp.route('/admin/offers/<int:offer_id>/delete', methods=['POST'])
def delete_offer(offer_id):
    if session.get('role') != 'admin':
        return "Access Denied", 403
    offer = Offer.query.get_or_404(offer_id)
    db.session.delete(offer)
    db.session.commit()
    flash('تم حذف العرض.', 'success')
    return redirect(url_for('main.admin_offers'))



@main_bp.route('/pos')
def pos_dashboard():
    # السماح فقط للمحاسب أو المدير
    if session.get('role') not in ['admin', 'accountant']:
        return "Access Denied", 403

    # جلب جميع الموظفين (الذين يمكن استلام العملاء)
    employees = Employee.query.all()  # هنا بدل User.query
    customers = Customer.query.all()
    services = Service.query.all()
    sale_items = Inventory.query.filter_by(for_sale=True).all()
    # تعبئة تلقائية عند قدوم cid من مسح بطاقة الولاء
    cid = request.args.get('cid', type=int)
    prefill_customer = Customer.query.get(cid) if cid else None
    
    return render_template(
        'pos_dashboard.html',
        employees=employees,
        customers=customers,
        services=services,
        sale_items=sale_items,
        prefill_customer=prefill_customer
    )


@main_bp.route('/products')
def products_page():
    # السماح فقط للمحاسب أو المدير
    if session.get('role') not in ['admin', 'accountant']:
        return "Access Denied", 403

    # تقسيم المنتجات إلى قسمين: استهلاك داخلي وبيع
    consumption_items = Inventory.query.filter_by(for_sale=False).all()
    sale_items = Inventory.query.filter_by(for_sale=True).all()
    return render_template('products.html', consumption_items=consumption_items, sale_items=sale_items)


@main_bp.route('/products/update_item', methods=['POST'])
def update_product_item():
    # مسموح للمدير فقط تعديل البيع والسعر
    if session.get('role') != 'admin':
        return "Access Denied", 403

    item_id = request.form.get('item_id')
    for_sale_val = request.form.get('for_sale')
    sale_price_val = request.form.get('sale_price')

    item = Inventory.query.get_or_404(item_id)

    # تحديث حالة البيع
    if for_sale_val is not None:
        item.for_sale = True if str(for_sale_val).lower() in ['1', 'true', 'yes', 'on'] else False

    # تحديث سعر البيع عند تفعيله
    if sale_price_val is not None and sale_price_val != '':
        try:
            item.sale_price = Decimal(str(sale_price_val))
        except Exception:
            flash('قيمة السعر غير صحيحة', 'danger')
            return redirect(url_for('main.products_page'))
    elif not item.for_sale:
        # إذا ألغي البيع احذف السعر
        item.sale_price = None

    db.session.commit()
    flash('تم تحديث المنتج بنجاح', 'success')
    return redirect(url_for('main.products_page'))











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
        for_sale_val = request.form.get('for_sale')
        sale_price_val = (request.form.get('sale_price') or '').strip()

        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join('static/uploads/inventory', filename))
                image_url = url_for('static', filename=f'uploads/inventory/{filename}')

        # تحديد خصائص البيع
        is_for_sale = True if (for_sale_val and str(for_sale_val).lower() in ['1','true','yes','on']) else False

        sale_price = None
        if is_for_sale and sale_price_val:
            try:
                sale_price = Decimal(str(sale_price_val))
                if sale_price < 0:
                    sale_price = None
            except Exception:
                sale_price = None

        new_item = Inventory(
            product=product,
            quantity=quantity,
            reorder_level=reorder_level,
            image_url=image_url,
            for_sale=is_for_sale,
            sale_price=sale_price
        )
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


@main_bp.route('/add_customer', methods=['POST'])
def add_customer():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = (request.form.get('email', '') or '').strip() or None

    if not name or not phone:
        flash('الاسم ورقم الهاتف مطلوبان', 'danger')
        return redirect(url_for('main.customers'))

    existing = Customer.query.filter_by(phone=phone).first()
    if existing:
        flash('هذا العميل موجود بالفعل برقم الهاتف المدخل', 'warning')
        return redirect(url_for('main.customers'))

    customer = Customer(name=name, phone=phone, email=email)
    db.session.add(customer)
    db.session.commit()
    flash(f'تمت إضافة العميل {name} بنجاح', 'success')
    return redirect(url_for('main.customers'))


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


@main_bp.route('/reports/monthly')
def monthly_reports():
    if session.get('role') not in ['admin', 'accountant']:
        return "Access Denied", 403

    # Parse month filter (YYYY-MM), default to current month
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

    # Compute end of month (first day of next month)
    if period_start.month == 12:
        period_end = date(period_start.year + 1, 1, 1)
    else:
        period_end = date(period_start.year, period_start.month + 1, 1)

    # Finance totals for the period
    total_revenue = (
        db.session.query(func.coalesce(func.sum(Revenue.amount), 0))
        .filter(Revenue.date >= period_start, Revenue.date < period_end)
        .scalar()
    )
    total_expenses = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.date >= period_start, Expense.date < period_end)
        .scalar()
    )
    total_salaries = (
        db.session.query(func.coalesce(func.sum(Salary.amount), 0))
        .filter(Salary.date >= period_start, Salary.date < period_end)
        .scalar()
    )

    # Normalize to Decimal
    total_revenue = total_revenue if isinstance(total_revenue, Decimal) else Decimal(str(total_revenue or 0))
    total_expenses = total_expenses if isinstance(total_expenses, Decimal) else Decimal(str(total_expenses or 0))
    total_salaries = total_salaries if isinstance(total_salaries, Decimal) else Decimal(str(total_salaries or 0))

    total_profit = total_revenue - (total_expenses + total_salaries)

    # Overall bookings count in the period (completed)
    completed_bookings_count = (
        db.session.query(func.count(Booking.id))
        .filter(
            Booking.date >= period_start,
            Booking.date < period_end,
            Booking.status == 'completed'
        )
        .scalar()
    )

    # Employee stats within the month
    employees_stats = (
        db.session.query(
            Employee.id,
            Employee.name,
            func.count(Booking.id).label('bookings_count'),
            func.coalesce(func.sum(Service.price), 0).label('income_total')
        )
        .outerjoin(
            Booking,
            and_(
                Booking.employee_id == Employee.id,
                Booking.date >= period_start,
                Booking.date < period_end,
                Booking.status == 'completed'
            )
        )
        .outerjoin(Service, Service.id == Booking.service_id)
        .group_by(Employee.id)
        .order_by(func.coalesce(func.sum(Service.price), 0).desc())
        .all()
    )

    return render_template(
        'monthly_reports.html',
        month_str=month_str,
        period_start=period_start,
        period_end=period_end,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        total_salaries=total_salaries,
        total_profit=total_profit,
        completed_bookings_count=completed_bookings_count,
        employees_stats=employees_stats
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
    current_user_id = session.get('user_id')
    employee = Employee.query.filter_by(user_id=current_user_id).first()
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

    current_user_id = session.get('user_id')
    employee = Employee.query.filter_by(user_id=current_user_id).first()
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

    current_user_id = session.get('user_id')
    employee = Employee.query.filter_by(user_id=current_user_id).first()
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

        # زيادة عدد زيارات العميل عند اكتمال الحجز لأول مرة
        if booking.customer_id:
            try:
                customer = Customer.query.get(booking.customer_id)
            except Exception:
                customer = None
            if customer:
                customer.visits = (customer.visits or 0) + 1

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

        # تحقق من وجود وقت محدد
        if not booking_time:
            flash("يرجى اختيار وقت الحجز من القائمة.", "danger")
            return redirect(url_for('main.pos_bookings'))

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

        # التحقق من التعارضات على جانب الخادم
        try:
            date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
            time_obj = datetime.strptime(booking_time, '%H:%M').time()
        except Exception:
            flash("صيغة التاريخ أو الوقت غير صحيحة.", "danger")
            return redirect(url_for('main.pos_bookings'))

        service = Service.query.get(service_id)
        duration = (service.duration_minutes or 30) if service else 30
        start_dt = datetime.combine(date_obj, time_obj)
        end_dt = start_dt + timedelta(minutes=duration)

        # احضر حجوزات الموظف لنفس اليوم وتحقق من التداخل
        existing_bookings = Booking.query.filter_by(employee_id=employee.id, date=date_obj).all()
        conflict_found = False
        for b in existing_bookings:
            b_service = Service.query.get(b.service_id)
            b_dur = (b_service.duration_minutes or 30) if b_service else 30
            b_start = datetime.combine(date_obj, b.time)
            b_end = b_start + timedelta(minutes=b_dur)
            if max(start_dt, b_start) < min(end_dt, b_end):
                conflict_found = True
                break

        if conflict_found:
            flash("الوقت المختار يتعارض مع حجز آخر لهذا الموظف.", "danger")
            return redirect(url_for('main.pos_bookings'))

        # إنشاء الحجز
        booking = Booking(
            customer_id=customer.id,
            service_id=service_id,
            employee_id=employee.id,
            date=date_obj,
            time=time_obj,
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
    # إعادة التوجيه إلى الواجهة العامة في الطلبات GET
    if request.method == 'GET':
        return redirect(url_for('main.home'))

    # POST: تسجيل حجز جديد من واجهة العملاء
    customer_name = request.form.get('customer_name')
    customer_phone = request.form.get('customer_phone')
    service_id = request.form.get('service_id')
    employee_id = request.form.get('employee_id')
    booking_date = request.form.get('booking_date')
    booking_time = request.form.get('booking_time')

    # تحقق من الوقت
    if not booking_time:
        flash("يرجى اختيار وقت الحجز من القائمة.", "danger")
        return redirect(url_for('main.home'))

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
        return redirect(url_for('main.home'))

    # إنشاء الحجز
    booking = Booking(
        customer_id=customer.id,
        service_id=service_id,
        employee_id=employee.id,
        date=datetime.strptime(booking_date, '%Y-%m-%d').date(),
        time=datetime.strptime(booking_time, '%H:%M').time(),
        status='booked'
    )
    db.session.add(booking)
    db.session.commit()
    flash("تم تسجيل الحجز بنجاح!", "success")
    return redirect(url_for('main.home'))



@main_bp.route('/api/available_times')
def available_times():
    """إرجاع قائمة بالأوقات المتاحة لموظف معيّن بتاريخ وخدمة محددين.

    المعايير:
    - service_id: الخدمة المطلوبة (لاشتقاق مدة التنفيذ)
    - employee_id: الموظف الذي سينفذ الخدمة (لتجنّب التعارضات)
    - date: التاريخ بصيغة YYYY-MM-DD
    """
    service_id = request.args.get('service_id')
    employee_id = request.args.get('employee_id')
    date_str = request.args.get('date')

    # تحقق من المعايير الأساسية
    if not service_id or not employee_id or not date_str:
        return {'times': []}

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        return {'times': []}

    # مدة الخدمة المطلوبة
    service = Service.query.get(service_id)
    service_duration = (service.duration_minutes or 30) if service else 30

    # نافذة العمل العامة (9:00 إلى 18:00 بنصف ساعة)
    working_start_hour = 9
    working_end_hour = 18
    step_minutes = 30

    def to_dt(h, m):
        return datetime.combine(date_obj, datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time())

    day_start = to_dt(working_start_hour, 0)
    day_end = to_dt(working_end_hour, 0)

    # احضر حجوزات الموظف في ذلك اليوم
    employee_bookings = Booking.query.filter_by(employee_id=employee_id, date=date_obj).all()

    # ابنِ فترات الانشغال بحسب مدة كل خدمة محجوزة
    busy_intervals = []
    for b in employee_bookings:
        b_service = Service.query.get(b.service_id)
        b_duration = (b_service.duration_minutes or 30) if b_service else 30
        b_start = datetime.combine(date_obj, b.time)
        b_end = b_start + timedelta(minutes=b_duration)
        busy_intervals.append((b_start, b_end))

    def overlaps(a_start, a_end, b_start, b_end):
        return max(a_start, b_start) < min(a_end, b_end)

    # لا نقترح أوقاتاً في الماضي لليوم الحالي
    now = datetime.utcnow()
    is_today = (date_obj == now.date())

    # ولّد كل نقاط البداية المحتملة وفق خطوة 30 دقيقة بشرط أن تتسع المدة كاملة داخل يوم العمل
    candidates = []
    cursor = day_start
    while cursor + timedelta(minutes=service_duration) <= day_end:
        if not (is_today and cursor <= now):
            candidates.append(cursor)
        cursor += timedelta(minutes=step_minutes)

    available = []
    for start_dt in candidates:
        end_dt = start_dt + timedelta(minutes=service_duration)
        conflict = any(overlaps(start_dt, end_dt, bs, be) for (bs, be) in busy_intervals)
        if not conflict:
            available.append(start_dt.strftime('%H:%M'))

    return {'times': available}


# -----------------------------
# Public Gallery Pages
# -----------------------------
def _load_gallery_categories():
    """Scan static/uploads/gallery and build a list of categories with meta.

    Returns list of dicts: {key, title, cover_url}
    """
    base_root = os.path.join('static', 'uploads', 'gallery')
    os.makedirs(base_root, exist_ok=True)

    categories = []
    for name in sorted(os.listdir(base_root)):
        dir_path = os.path.join(base_root, name)
        if not os.path.isdir(dir_path):
            continue

        # Defaults
        title = name
        cover_rel = None

        # Read meta.json if exists
        meta_path = os.path.join(dir_path, 'meta.json')
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    title = meta.get('title') or title
                    cover_rel = meta.get('cover') or None
            except Exception:
                pass

        cover_url = None
        if cover_rel:
            cover_url = url_for('static', filename=f'uploads/gallery/{name}/{cover_rel}')
        else:
            # Fallback: first image in directory
            allowed_ext = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
            try:
                for filename in sorted(os.listdir(dir_path)):
                    _, ext = os.path.splitext(filename.lower())
                    if ext in allowed_ext:
                        cover_url = url_for('static', filename=f'uploads/gallery/{name}/{filename}')
                        break
            except FileNotFoundError:
                pass

        categories.append({
            'key': name,
            'title': title,
            'cover_url': cover_url
        })

    return categories


@main_bp.route('/gallery')
def gallery():
    categories = _load_gallery_categories()
    return render_template('gallery.html', categories=categories)


@main_bp.route('/gallery/<string:category_key>')
def gallery_category(category_key):
    # Directory path under static/uploads/gallery/<category>
    base_dir = os.path.join('static', 'uploads', 'gallery', category_key)
    if not os.path.isdir(base_dir):
        return "Category not found", 404

    # Determine title from meta.json if present
    category_title = category_key
    meta_path = os.path.join(base_dir, 'meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                category_title = meta.get('title') or category_title
        except Exception:
            pass

    allowed_ext = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    images = []
    try:
        for filename in sorted(os.listdir(base_dir)):
            _, ext = os.path.splitext(filename.lower())
            if ext in allowed_ext:
                images.append(
                    url_for('static', filename=f'uploads/gallery/{category_key}/{filename}')
                )
    except FileNotFoundError:
        images = []

    return render_template(
        'gallery_category.html',
        category_key=category_key,
        category_title=category_title,
        images=images
    )


# -----------------------------
# Admin: Upload Gallery Images
# -----------------------------
@main_bp.route('/admin/gallery', methods=['GET', 'POST'])
def admin_gallery():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    # Handle POST actions: create_category or upload_images
    if request.method == 'POST':
        action = request.form.get('action') or 'upload_images'
        allowed_ext = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        base_root = os.path.join('static', 'uploads', 'gallery')
        os.makedirs(base_root, exist_ok=True)

        if action == 'create_category':
            category_key = (request.form.get('key') or '').strip()
            title = (request.form.get('title') or '').strip()
            cover_file = request.files.get('cover')

            if not category_key or not title or not cover_file or cover_file.filename == '':
                flash('الرجاء إدخال المفتاح والعنوان واختيار صورة الغلاف.', 'danger')
                return redirect(url_for('main.admin_gallery'))

            # Sanitize directory name
            category_key = secure_filename(category_key).lower()
            dir_path = os.path.join(base_root, category_key)
            if os.path.exists(dir_path):
                flash('الفئة موجودة بالفعل.', 'warning')
                return redirect(url_for('main.admin_gallery'))

            os.makedirs(dir_path, exist_ok=True)

            # Save cover image
            name = secure_filename(cover_file.filename)
            _, ext = os.path.splitext(name.lower())
            if ext not in allowed_ext:
                flash('امتداد صورة الغلاف غير مسموح.', 'danger')
                return redirect(url_for('main.admin_gallery'))
            cover_name = f"cover_{uuid.uuid4().hex}{ext}"
            cover_file.save(os.path.join(dir_path, cover_name))

            # Write meta.json
            meta = {"title": title, "cover": cover_name}
            with open(os.path.join(dir_path, 'meta.json'), 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            flash('تم إنشاء الفئة ورفع صورة الغلاف بنجاح.', 'success')
            return redirect(url_for('main.admin_gallery'))

        # Default: upload images to existing category
        category_key = request.form.get('category')
        base_dir = os.path.join(base_root, category_key)
        if not os.path.isdir(base_dir):
            flash('فئة غير موجودة.', 'danger')
            return redirect(url_for('main.admin_gallery'))

        files = request.files.getlist('images')
        if not files:
            flash('يرجى اختيار صورة واحدة على الأقل.', 'warning')
            return redirect(url_for('main.admin_gallery'))

        saved_count = 0
        for f in files:
            if not f or f.filename == '':
                continue
            name = secure_filename(f.filename)
            _, ext = os.path.splitext(name.lower())
            if ext not in allowed_ext:
                continue
            unique_name = f"{uuid.uuid4().hex}{ext}"
            f.save(os.path.join(base_dir, unique_name))
            saved_count += 1

        if saved_count:
            flash(f'تم رفع {saved_count} صورة بنجاح.', 'success')
        else:
            flash('لم يتم رفع أي صور. تأكد من الامتداد المسموح.', 'warning')

        return redirect(url_for('main.admin_gallery'))

    # GET: load categories dynamically
    categories = _load_gallery_categories()
    return render_template('admin_gallery.html', categories=categories)

# -----------------------------
# POS: Create Sale and Invoice
# -----------------------------
@main_bp.route('/pos/sales/create', methods=['POST'])
def create_sale():
    # السماح فقط للمحاسب أو المدير
    if session.get('role') not in ['accountant', 'admin']:
        return "Access Denied", 403

    item_type = (request.form.get('item_type') or 'service').strip()
    service_id = request.form.get('service_id')
    inventory_id = request.form.get('inventory_id')
    employee_id = request.form.get('employee_id')
    customer_name = request.form.get('customer_name')
    customer_phone = request.form.get('customer_phone')
    quantity_str = request.form.get('quantity', '1')
    payment_method = (request.form.get('payment_method') or 'cash').strip().lower()
    paid_amount_str = (request.form.get('paid_amount') or '0').strip()
    payment_reference = (request.form.get('payment_reference') or '').strip()
    due_date_str = (request.form.get('due_date') or '').strip()

    try:
        quantity = int(quantity_str)
        if quantity <= 0:
            quantity = 1
    except Exception:
        quantity = 1

    # التأكد من وجود العنصر والموظف
    service = None
    inventory_item = None
    if item_type == 'product':
        if not inventory_id:
            flash("المنتج غير محدد!", "danger")
            return redirect(url_for('main.pos_dashboard'))
        inventory_item = Inventory.query.get(inventory_id)
        if not inventory_item or not inventory_item.for_sale or not inventory_item.sale_price:
            flash("المنتج غير صالح للبيع!", "danger")
            return redirect(url_for('main.pos_dashboard'))
    else:
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
    if item_type == 'product':
        unit_price = Decimal(str(inventory_item.sale_price))
    else:
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

    if item_type == 'product':
        sale_item = SaleItem(
            sale_id=sale.id,
            inventory_id=inventory_item.id,
            quantity=quantity,
            price=unit_price
        )
    else:
        sale_item = SaleItem(
            sale_id=sale.id,
            service_id=service.id,
            quantity=quantity,
            price=unit_price
        )
    db.session.add(sale_item)

    # خصم المخزون للمنتج المباع
    if item_type == 'product':
        if quantity > inventory_item.quantity:
            db.session.rollback()
            flash('الكمية المطلوبة أكبر من المخزون الحالي!', 'danger')
            return redirect(url_for('main.pos_dashboard'))
        inventory_item.quantity -= quantity

    # معالجة الدفع
    allowed_methods = {'cash', 'card', 'transfer', 'prepaid', 'deferred'}
    if payment_method not in allowed_methods:
        payment_method = 'cash'

    # due_date للمدفوعات المؤجلة
    due_date = None
    if payment_method == 'deferred':
        try:
            if due_date_str:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            else:
                due_date = (datetime.utcnow() + timedelta(days=7)).date()
        except Exception:
            due_date = (datetime.utcnow() + timedelta(days=7)).date()
        sale.due_date = due_date

    # إنشاء سجل الدفع إن وجد مبلغ مدفوع
    try:
        paid_amount = Decimal(str(paid_amount_str))
    except Exception:
        paid_amount = Decimal('0')
    if paid_amount < 0:
        paid_amount = Decimal('0')

    if paid_amount > 0:
        payment = Payment(
            sale_id=sale.id,
            method=payment_method,
            amount=min(paid_amount, total_amount),
            reference=payment_reference or None
        )
        db.session.add(payment)
        # Loyalty: award 1 point if a known customer pays more than 5
        try:
            effective_paid = min(paid_amount, total_amount)
        except Exception:
            effective_paid = paid_amount
        if customer and effective_paid > Decimal('5'):
            customer.loyalty_points = (customer.loyalty_points or 0) + 1

    # تحديد حالة الفاتورة بناءً على إجمالي المدفوعات المسجلة
    # نضمن إدراج الدفع الجديد في قاعدة البيانات قبل الحساب
    db.session.flush()
    total_paid = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.sale_id == sale.id).scalar()
    try:
        total_paid = total_paid if isinstance(total_paid, Decimal) else Decimal(str(total_paid or 0))
    except Exception:
        total_paid = Decimal('0')
    if total_paid <= Decimal('0'):
        sale.status = 'unpaid'
    elif total_paid >= total_amount:
        sale.status = 'paid'
    else:
        sale.status = 'partial'

    # تسجيل الإيراد على أساس المبلغ المستلم فقط
    if paid_amount > 0:
        item_label = service.name if service else (inventory_item.product if inventory_item else 'Item')
        revenue = Revenue(
            source=f"POS - {item_label}",
            amount=min(paid_amount, total_amount),
            date=datetime.utcnow().date()
        )
        db.session.add(revenue)

    # زيادة عدد زيارات العميل عند إنشاء عملية بيع مرتبطة بعميل
    if customer:
        customer.visits = (customer.visits or 0) + 1

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


# -----------------------------
# Admin: Unpaid/Partial Invoices Management
# -----------------------------
@main_bp.route('/admin/invoices')
def unpaid_invoices():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    unpaid_sales = Sale.query.filter(Sale.status == 'unpaid').order_by(Sale.date.desc()).all()
    partial_sales = Sale.query.filter(Sale.status == 'partial').order_by(Sale.date.desc()).all()
    return render_template('unpaid_invoices.html', unpaid_sales=unpaid_sales, partial_sales=partial_sales)


@main_bp.route('/admin/invoices/<int:sale_id>/add_payment', methods=['POST'])
def add_payment_to_invoice(sale_id):
    if session.get('role') != 'admin':
        return "Access Denied", 403

    sale = Sale.query.get_or_404(sale_id)

    action = (request.form.get('action') or 'add_payment').strip()
    method = (request.form.get('method') or 'cash').strip().lower()
    reference = (request.form.get('reference') or '').strip() or None

    allowed_methods = {'cash', 'card', 'transfer', 'prepaid', 'deferred'}
    if method not in allowed_methods:
        method = 'cash'

    # Compute remaining balance
    try:
        paid_sum = sum((p.amount for p in sale.payments), Decimal('0'))
    except Exception:
        paid_sum = Decimal('0')
    try:
        total_amount = Decimal(str(sale.total_amount))
    except Exception:
        total_amount = Decimal('0')
    remaining = total_amount - paid_sum

    if action == 'mark_paid':
        pay_amount = remaining
    else:
        amount_str = (request.form.get('amount') or '0').strip()
        try:
            pay_amount = Decimal(amount_str)
        except Exception:
            pay_amount = Decimal('0')

    if pay_amount <= 0:
        flash('المبلغ غير صالح.', 'danger')
        return redirect(url_for('main.unpaid_invoices'))

    effective_amount = pay_amount if pay_amount <= remaining else remaining
    if effective_amount <= 0:
        flash('لا يوجد رصيد متبقٍ لهذه الفاتورة.', 'warning')
        return redirect(url_for('main.unpaid_invoices'))

    payment = Payment(
        sale_id=sale.id,
        method=method,
        amount=effective_amount,
        reference=reference
    )
    db.session.add(payment)

    # Record revenue for received payment
    try:
        item_label = None
        if sale.items and sale.items[0].service:
            item_label = sale.items[0].service.name
        elif sale.items and sale.items[0].inventory:
            item_label = sale.items[0].inventory.product
        else:
            item_label = f"Sale #{sale.id}"
        revenue = Revenue(
            source=f"POS - Payment for {item_label}",
            amount=effective_amount,
            date=datetime.utcnow().date()
        )
        db.session.add(revenue)
    except Exception:
        # Fallback: do not block if label resolution fails
        pass

    # Update sale status based on new paid sum
    new_paid_sum = paid_sum + effective_amount
    if new_paid_sum <= Decimal('0'):
        sale.status = 'unpaid'
    elif new_paid_sum >= total_amount:
        sale.status = 'paid'
    else:
        sale.status = 'partial'

    db.session.commit()
    flash('تم تسجيل الدفع وتحديث حالة الفاتورة.', 'success')
    return redirect(url_for('main.unpaid_invoices'))
