from service import app
from flask import jsonify, request
from service.models import Venue, Field, CartItem, Product, Pitch, cart_item_schema, cart_items_schema, PromoCode
from datetime import datetime, timedelta
from service import db
import jwt
import json


# Create
@app.route("/cartitem", methods=["POST"])
def add_cartitem():
    token = request.headers["token"]
    venue_name = request.json["venue"]
    field_type = request.json["field"]
    pitch_name = request.json["pitch"]
    start_time = request.json["timeStart"]
    end_time = request.json["timeEnd"]
    expiry_date = datetime.now() + timedelta(minutes=20)
    product_name = request.json["product"]   
    code_name = request.json.get("code")

    venue = Venue.query.filter_by(name=venue_name).first()

    venue_id = venue.id

    product = Product.query.filter_by(name=product_name).first()
    product_id = product.id
    amount = product.price

    field = Field.query.filter_by(field_type=field_type, venue_id=venue_id).first()
    field_id = field.id

    pitch = Pitch.query.filter_by(name=pitch_name, field_id=field_id).first()
    pitch_id = pitch.id

    promocode = PromoCode.query.filter_by(code=code_name).first()
    promocode_id = promocode.id

    if code_name is not None:
        promocode = PromoCode.query.filter_by(code=code_name).first()
        x = promocode.discount_type
        if x == "Percentage":
            discount_amount = (100-promocode.discount)*amount/100
        elif x == "Price":
            discount_amount = (amount - promocode.discount)
        else:
            discount_amount = amount

    file = open("instance/key.key", "rb")
    key = file.read()
    file.close()

    customer_id = jwt.decode(token, key, algorithms=['HS256'])["customer_id"]

    newcartitem = CartItem(venue_id, field_id, pitch_id, promocode_id, customer_id, start_time, end_time, expiry_date, product_id, amount, discount_amount)
    db.session.add(newcartitem)
    db.session.commit()
    return cart_item_schema.jsonify(newcartitem)

# Update
@app.route("/cartitem/<Id>", methods=["PUT"])
def update_cartitem(Id):
    cartitem = CartItem.query.get(Id) 
    product_name = request.json["product"]

    
    product = Product.query.filter_by(name=product_name).first()
    product_id = product.id
    amount = product.price

    code_id = cartitem.promocode_id
    print(code_id)

    promocode = PromoCode.query.get(code_id)

    if promocode is not None:
        x = promocode.discount_type
        if x == "Percentage":
            discount_amount = (100-promocode.discount)*amount/100
        elif x == "Price":
            discount_amount = (amount - promocode.discount)
        else:
            discount_amount = amount

    cartitem.product_id = product_id
    cartitem.discount_amount = discount_amount
    cartitem.amount = amount

    db.session.commit()

    return cart_item_schema.jsonify(cartitem)

# Get
@app.route("/cartitem", methods=["GET"])
def get_cartitem():
    token = request.headers["token"]

    file = open("instance/key.key", "rb")
    key = file.read()
    file.close()

    customerid = jwt.decode(token, key, algorithms=['HS256'])["customer_id"]

    cartitems = CartItem.query.filter_by(customer_id=customerid).filter(CartItem.expiry_date > datetime.now()).all()
    result = cart_items_schema.dump(cartitems)
    return jsonify(result)

# Get cartitem by Id
@app.route("/cartitem/<Id>", methods=["GET"])
def get_cartitem_by_id(Id):
    cartitems = CartItem.query.get(Id)
    return cart_item_schema.jsonify(cartitems)

# Delete
@app.route("/cartitem/<Id>", methods=["DELETE"])
def delete_cartitem(Id):
    cartitem = CartItem.query.get(Id)
    db.session.delete(cartitem)
    db.session.commit()

    return (json.dumps({'message': 'success'}), 200, {'ContentType': 'application/json'})