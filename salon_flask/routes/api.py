from flask import Blueprint, jsonify, request
from models import Customer
from extensions import db
from flask_jwt_extended import jwt_required

api_bp = Blueprint('api', __name__)

# basic CRUD endpoints for Customer as example
@api_bp.route('/customers', methods=['GET'])
@jwt_required()
def list_customers():
    items = Customer.query.all()
    return jsonify([{'id':c.id,'name':c.name,'phone':c.phone,'email':c.email} for c in items])

@api_bp.route('/customers', methods=['POST'])
@jwt_required()
def create_customer():
    data = request.get_json()
    c = Customer(name=data['name'], phone=data['phone'], email=data.get('email'))
    db.session.add(c)
    db.session.commit()
    return jsonify({'id': c.id}), 201
