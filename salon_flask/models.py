from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

# simple user model for auth (roles: admin, staff, accountant, store)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(30), default='staff')  # admin, staff, accountant, store

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120))
    visits = db.Column(db.Integer, default=0)
    loyalty_points = db.Column(db.Integer, default=0)

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100))
    work_hours = db.Column(db.String(100))
    commission_rate = db.Column(db.Numeric(5,2), default=0.0)
    role = db.Column(db.String(30), default='staff')  # admin, staff, accountant
   
    # ربط الموظف بالمستخدم
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='employee')

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10,2), nullable=False)
    duration_minutes = db.Column(db.Integer)
    image_url = db.Column(db.String(200))
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    status = db.Column(db.String(20))

    customer = db.relationship('Customer', backref='bookings', lazy=True)
    service = db.relationship('Service', backref='bookings', lazy=True)
    employee = db.relationship('Employee', backref='bookings', lazy=True)



class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    notes = db.Column(db.Text)                  # العمود الجديد للملاحظات
    amount_paid = db.Column(db.Numeric(10,2))   # العمود الجديد للمبالغ المدفوعة

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=10)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    image_url = db.Column(db.String(200)) 
    # تحديد إن كان المنتج مخصص للبيع أم للاستهلاك الداخلي
    for_sale = db.Column(db.Boolean, default=False)
    # سعر البيع الذي يحدده المدير فقط عند تفعيل البيع
    sale_price = db.Column(db.Numeric(10,2), nullable=True)
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Revenue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(100))
    amount = db.Column(db.Numeric(10,2))
    date = db.Column(db.Date)




class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    total_amount = db.Column(db.Numeric(10,2), default=0.0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='unpaid')  # unpaid, partial, paid
    due_date = db.Column(db.Date, nullable=True)  # للمدفوعات المؤجلة

    employee = db.relationship('Employee', backref='sales')
    customer = db.relationship('Customer', backref='sales')
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='sale', cascade='all, delete-orphan')

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Numeric(10,2))

    service = db.relationship('Service')


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    method = db.Column(db.String(20), nullable=False)  # cash, card, transfer, prepaid, deferred
    amount = db.Column(db.Numeric(10,2), nullable=False)
    reference = db.Column(db.String(120))  # رقم مرجعي للتحويل/البطاقة
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)





class Salary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.String(20), nullable=False)  # مثال: "سبتمبر 2025"
    date = db.Column(db.DateTime, default=datetime.utcnow)








class InventoryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    inventory = db.relationship('Inventory', backref='transactions')
    employee = db.relationship('Employee', backref='inventory_transactions')
