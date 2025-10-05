from flask import Blueprint, render_template, request, redirect, url_for, abort, send_file, session
from io import BytesIO
import qrcode
from models import Customer


loyalty_bp = Blueprint('loyalty', __name__, template_folder='../templates')


def build_membership_code(customer: Customer) -> str:
    return f"C-{customer.id:06d}"


@loyalty_bp.route('/loyalty')
def loyalty_dashboard():
    if session.get('role') != 'admin':
        return "Access Denied", 403
    query = (request.args.get('q') or '').strip()
    customers_query = Customer.query
    if query:
        customers_query = customers_query.filter(
            (Customer.name.ilike(f"%{query}%")) | (Customer.phone.ilike(f"%{query}%"))
        )
    customers = customers_query.order_by(Customer.id.desc()).all()
    return render_template('loyalty_dashboard.html', customers=customers, query=query, build_membership_code=build_membership_code)


@loyalty_bp.route('/loyalty/card/<int:customer_id>')
def loyalty_card(customer_id: int):
    customer = Customer.query.get_or_404(customer_id)
    card_url = url_for('loyalty.loyalty_card', customer_id=customer.id, _external=True)
    scan_url = url_for('loyalty.scan', cid=customer.id, _external=True)
    qr_url = url_for('loyalty.qr_png', customer_id=customer.id)
    membership_code = build_membership_code(customer)
    return render_template(
        'loyalty_card.html',
        customer=customer,
        card_url=card_url,
        scan_url=scan_url,
        qr_url=qr_url,
        membership_code=membership_code,
    )


@loyalty_bp.route('/loyalty/qr/<int:customer_id>.png')
def qr_png(customer_id: int):
    customer = Customer.query.get_or_404(customer_id)
    # Encode a scan URL that smartly redirects based on user (POS vs customer)
    qr_data = url_for('loyalty.scan', cid=customer.id, _external=True)
    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name=f"loyalty_{customer.id}.png")


@loyalty_bp.route('/loyalty/barcode/<int:customer_id>.png')
def barcode_png(customer_id: int):
    customer = Customer.query.get_or_404(customer_id)
    code_data = build_membership_code(customer)
    try:
        import barcode as _barcode
        from barcode.writer import ImageWriter
    except Exception:
        abort(500, description='إنشاء الباركود غير متاح حالياً. الرجاء تثبيت python-barcode.')
    code128 = _barcode.get('code128', code_data, writer=ImageWriter())
    buf = BytesIO()
    code128.write(buf, options={
        'write_text': False,
        'module_height': 18.0,
        'module_width': 0.4,
        'quiet_zone': 2.0
    })
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name=f"loyalty_barcode_{customer.id}.png")

@loyalty_bp.route('/loyalty/scan')
def scan():
    cid = request.args.get('cid', type=int)
    if not cid:
        abort(404)
    # If scanned by POS roles, redirect to POS with prefill
    if session.get('role') in ['admin', 'accountant', 'staff']:
        return redirect(url_for('main.pos_dashboard', cid=cid))
    # Otherwise show the public card
    return redirect(url_for('loyalty.loyalty_card', customer_id=cid))
