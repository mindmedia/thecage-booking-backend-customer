from service import app
from flask import jsonify, request
from service.models import TimingDiscount, timingdiscount_schema, Customer, CustomerOdoo, Venue, Field, CartItem, Product, Pitch, cart_item_schema, cart_items_schema, cart_item2s_schema, field2_schema, fields2_schema, venue_schema, product_schema, pitch_schema, PromoCode
from datetime import datetime, timedelta
from service import db
import jwt
import json
from instance.config import url, db as database, username, password, id
import xmlrpc.client
from threading import Timer


# Create
@app.route("/cartitem", methods=["POST"])
def add_cartitem():
    items = request.json["items"]
    tokenstr = request.headers["Authorization"]
    file = open("instance/key.key", "rb")
    key = file.read()
    file.close()
    tokenstr = tokenstr.split(" ")
    token = tokenstr[1]
    customer_id = jwt.decode(token, key, algorithms=['HS256'])["customer_id"]
    timestamp = datetime.now()
    timestamp_utc = datetime.now()-timedelta(hours=8)
    common = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/common")
    uid = common.authenticate(database, username, password, {})
    models = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/object")
    model_results = ""
    customer_odoo = CustomerOdoo.query.filter_by(customer_id=customer_id).first()
    customer_odoo_odoo_id = customer_odoo.odoo_id
    cartitems = CartItem.query.filter_by(customer_id=customer_id).filter(CartItem.expiry_date > datetime.now()).all()
    result = cart_items_schema.dump(cartitems)
    print(result)
    if (result == []):
        sales_order_id = models.execute_kw(
            database,
            uid,
            password,
            "sale.order",
            "create",
            [
                {
                    "date_order": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "partner_id": int(customer_odoo_odoo_id),
                    "user_id": int(id),
                }
            ],
            {
                "context": {
                    "tz": "Singapore"
                }
            }
        )
    else:
        customer = Customer.query.get(customer_id)
        customer_name = customer.name
        customer_phone_no = customer.phone_no
        sale_order = models.execute_kw(
            database,
            uid,
            password,
            "sale.order",
            "search_read",
            [[["partner_id", "=", f"{customer_name} ({customer_phone_no})"]]],
        )
        sales_order_id = sale_order[0]["id"]
    for i in items:
        pitch_id = i["pitchId"]
        start_time = i["booking_start"]
        end_time = i["booking_end"]
        expiry_date = datetime.now() + timedelta(minutes=20)
        product_id = i["productId"]   
        code_name = i.get("code")

        # venue = Venue.query.filter_by(name=venue_name).first()

        # venue_id = venue.id

        product = Product.query.get(product_id)
        amount = product.price

        # field = Field.query.filter_by(field_type=field_type, venue_id=venue_id).first()
        # field_id = field.id

        pitch = Pitch.query.get(pitch_id)
        new_pitch_id = pitch.id

        field_id = pitch.field_id
        field = Field.query.get(field_id)

        venue_id = field.venue_id

        promocode = PromoCode.query.filter_by(code=code_name).first()
        no_of_hours = (datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S') - datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')).total_seconds()/3600
        new_amount = amount*no_of_hours

        # check timing discount
        timingdiscount = timingdiscount_schema.dump(TimingDiscount.query.get(1))
        timingdiscount_date = datetime.date(datetime.strptime(timingdiscount.get('date'), '%Y-%m-%d'))
        if (datetime.date(datetime.today()) == timingdiscount_date):
            x = timingdiscount.get('discount_type')
            if x == "Percentage":
                new_amount = (100-timingdiscount.get('discount'))*new_amount/100
            elif x == "Price":
                new_amount = (new_amount - timingdiscount.get('discount'))
            else:
                new_amount = new_amount

        # check promo code usage
        if code_name is not None:
            promocode_id = promocode.id
            promocode = PromoCode.query.filter_by(code=code_name).first()
            x = promocode.discount_type
            if x == "Percent":
                discounted_amount = (100-promocode.discount)*new_amount/100
            elif x == "Price":
                discounted_amount = (new_amount - promocode.discount)
            else:
                discounted_amount = new_amount

        else:
            promocode_id = None
            discounted_amount = new_amount

        newcartitem = CartItem(venue_id, field_id, new_pitch_id, promocode_id, customer_id, start_time, end_time, expiry_date, product_id, new_amount, discounted_amount)
        db.session.add(newcartitem)

        booking_start = datetime.strftime(datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')-timedelta(hours=8), '%Y-%m-%d %H:%M:%S')
        booking_end = datetime.strftime(datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')-timedelta(hours=8), '%Y-%m-%d %H:%M:%S')
        product_qty = (datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S') - datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')).total_seconds()/3600
        product_name = (Product.query.get(product_id)).name
        product_odoo_id = (Product.query.get(product_id)).odoo_id
        pitch_odoo_id = (Pitch.query.get(pitch_id)).odoo_id
        venue_odoo_id = (Field.query.get(field_id)).odoo_id

        model_results = models.execute_kw(
            database,
            uid,
            password,
            "sale.order.line",
            "create",
            [
                {
                    "product_uos_qty": product_qty,
                    "product_uom_qty": product_qty,
                    "booking_start": booking_start,
                    "booking_end": booking_end,
                    "name": product_name,
                    "order_id": int(sales_order_id),
                    "product_id": int(product_odoo_id),
                    "pitch_id": int(pitch_odoo_id),
                    "venue_id": int(venue_odoo_id),
                    "booking_state": "in_progress",
                    "partner_id": int(customer_odoo_odoo_id)
                },
            ],
            {
                "context": {
                    "tz": "Singapore"
                }
            }
        )
        print(model_results)

    db.session.commit()
    def cancelOrder():
        sale_order = models.execute_kw(
            database,
            uid,
            password,
            "sale.order",
            "search_read",
            [[["id", "=", sales_order_id]]],
        )
        if (sale_order[0]["state"] == "draft"):
            modelResults = models.execute_kw(database, uid, password,
                'sale.order', 'write',
                [[int(sales_order_id)], {"state": 'cancel'}],
            )
    t = Timer(1200.0, cancelOrder)
    t.start()
    return (request.json)

# Update
# @app.route("/cartitem/<Id>", methods=["PUT"])
# def update_cartitem(Id):
#     cartitem = CartItem.query.get(Id)
#     product_name = request.json["product"]


#     product = Product.query.filter_by(name=product_name).first()
#     product_id = product.id
#     amount = product.price

#     code_id = cartitem.promocode_id
#     print(code_id)

#     if code_id is not None:
#         promocode = PromoCode.query.get(code_id)
#         x = promocode.discount_type
#         if x == "Percentage":
#             discount_amount = (100-promocode.discount)*amount/100
#         elif x == "Price":
#             discount_amount = (amount - promocode.discount)
#         else:
#             discount_amount = amount
#     else:
#         discount_amount = amount

#     cartitem.product_id = product_id
#     cartitem.discount_amount = discount_amount
#     cartitem.amount = amount

#     db.session.commit()

#     return cart_item_schema.jsonify(cartitem)

# Get customer's cart items
@app.route("/cartitem", methods=["GET"])
def get_cartitem():

    return_list = {}
    tokenstr = request.headers["Authorization"]

    file = open("instance/key.key", "rb")
    key = file.read()
    file.close()
    tokenstr = tokenstr.split(" ")
    token = tokenstr[1]
    customerid = jwt.decode(token, key, algorithms=['HS256'])["customer_id"]
    cartitems = CartItem.query.filter_by(customer_id=customerid).filter(CartItem.expiry_date > datetime.now()).all()
    # cartitems = CartItem.query.filter_by(customer_id=customerid).all()
    result = cart_items_schema.dump(cartitems)
    return_list.setdefault('items', [])
    for one_result in result:

        one_result["fieldType"] = one_result.pop("field_id")
        one_result["pitchName"] = one_result.pop("pitch_id")
        one_result["productName"] = one_result.pop("product_id")
        one_result["venueName"] = one_result.pop("venue_id")
        one_result["discountAmount"] = one_result.pop("discounted_amount")
        one_result["startTime"] = one_result.pop("start_time")
        one_result["endTime"] = one_result.pop("end_time")

        field = Field.query.filter_by(id=one_result["fieldType"]).first()
        result = field2_schema.dump(field)
        one_result["fieldType"] = result["field_type"]

        pitch = Pitch.query.filter_by(id=one_result["pitchName"]).first()
        result = pitch_schema.dump(pitch)
        one_result["pitchName"] = result["name"]

        product = Product.query.filter_by(id=one_result["productName"]).first()
        result = product_schema.dump(product)
        one_result["productName"] = result["name"]

        venue = Venue.query.filter_by(id=one_result["venueName"]).first()
        result = venue_schema.dump(venue)
        one_result["venueName"] = result["name"]

        return_list['items'].append(one_result)
    return jsonify(return_list)

# Get all cart items
@app.route("/allcartitems", methods=["GET"])
def get_allcartitems():

    cartitems = CartItem.query.filter(CartItem.expiry_date > datetime.now()).all()
    result = cart_item2s_schema.dump(cartitems)
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
    pitch_id = cartitem.pitch_id
    venue_id = cartitem.venue_id
    start_time = cartitem.start_time
    end_time = cartitem.end_time
    field_id = cartitem.field_id
    pitch_odoo_id = (Pitch.query.get(pitch_id)).odoo_id
    venue_odoo_id = (Field.query.filter_by(id=field_id).first()).odoo_id

    common = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/common")
    uid = common.authenticate(database, username, password, {})
    models = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/object")

    venue_name = models.execute_kw(database, uid, password,
        'pitch_booking.venue', 'search_read',
        [[['id', '=', str(venue_odoo_id)]]], {'fields': ['name']},
    )[0]["name"]
    pitch_name =  models.execute_kw(database, uid, password,
        'pitch_booking.pitch', 'search_read',
        [[['id', '=', pitch_odoo_id]]], {'fields': ['name']},
    )[0]["name"]

    common = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/common")
    uid = common.authenticate(database, username, password, {})
    models = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/object")
    order = models.execute_kw(
        database,
        uid,
        password,
        "sale.order.line",
        "search_read",
        [[["booking_start", "=", (start_time-timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")], ["booking_end", "=", (end_time-timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")], ["pitch_id", '=', pitch_name], ["venue_id", '=', venue_name]]],
        {'fields':
            [
                'id',
                "order_id"
            ]
        }
    )[0]
    sale_order_lines_search = models.execute_kw(
        database,
        uid,
        password,
        "sale.order.line",
        "search_read",
        [[["order_id", "=", order['order_id'][0]]]],
        {'fields':
            [
                'id', 
                "product_uos_qty",
                "product_uom_qty",
                "booking_start",
                "booking_end",
                "name",
                "order_id",
                "product_id",
                "pitch_id",
                "venue_id",
                "booking_state",
                "partner_id"
            ]
        }
    )
    sale_order = models.execute_kw(
        database,
        uid,
        password,
        "sale.order",
        "search_read",
        [[["id", "=", order['order_id'][0]]]],
        {'fields': ['id', 'date_order', 'partner_id', 'user_id']}
    )
    print(len(sale_order_lines_search))
    if (len(sale_order_lines_search) != 1):
        sales_order_new_id = models.execute_kw(
            database,
            uid,
            password,
            "sale.order",
            "create",
            [
                {
                    "date_order": sale_order[0]['date_order'],
                    "partner_id": sale_order[0]['partner_id'][0],
                    "user_id": sale_order[0]['user_id'][0],
                }
            ],
            {
                "context": {
                    "tz": "Singapore"
                }
            }
        )
    modelResults = models.execute_kw(database, uid, password,
        'sale.order', 'write',
        [[sale_order[0]['id']], {"state": "cancel"}],
    )
    for sale_order_line in sale_order_lines_search:
        if (sale_order_line['id'] != order['id']):
            model_results = models.execute_kw(
                database,
                uid,
                password,
                "sale.order.line",
                "create",
                [
                    {
                        "product_uos_qty": sale_order_line['product_uos_qty'],
                        "product_uom_qty": sale_order_line['product_uom_qty'],
                        "booking_start": sale_order_line['booking_start'],
                        "booking_end": sale_order_line['booking_end'],
                        "name": sale_order_line['name'],
                        "order_id": int(sales_order_new_id),
                        "product_id": int(sale_order_line['product_id'][0]),
                        "pitch_id": int(sale_order_line['pitch_id'][0]),
                        "venue_id": int(sale_order_line['venue_id'][0]),
                        "booking_state": "in_progress",
                        "partner_id": int(sale_order_line['partner_id'][0])
                    },
                ],
                {
                    "context": {
                        "tz": "Singapore"
                    }
                }
            )
    def cancelOrder():
        sale_order = models.execute_kw(
            database,
            uid,
            password,
            "sale.order",
            "search_read",
            [[["id", "=", sales_order_new_id]]],
        )
        if (sale_order[0]["state"] == "draft"):
            modelResults = models.execute_kw(database, uid, password,
                'sale.order', 'write',
                [[int(sales_order_new_id)], {"state": 'cancel'}],
            )
    t = Timer(60.0, cancelOrder)
    t.start()

    db.session.delete(cartitem)
    db.session.commit()

    return (json.dumps({'message': 'success'}), 200, {'ContentType': 'application/json'})


# Delete all cart items by customerId
@app.route("/cartitem", methods=["DELETE"])
def delete_all_cartitems():
    tokenstr = request.headers["Authorization"]

    file = open("instance/key.key", "rb")
    key = file.read()
    file.close()
    tokenstr = tokenstr.split(" ")
    token = tokenstr[1]
    customer_id = jwt.decode(token, key, algorithms=['HS256'])["customer_id"]
    customer = Customer.query.get(customer_id)
    customer_name = customer.name
    customer_phone_no = customer.phone_no
    print(customer_id)

    common = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/common")
    uid = common.authenticate(database, username, password, {})
    models = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/object")
    sale_orders = models.execute_kw(
        database,
        uid,
        password,
        "sale.order",
        "search_read",
        [[["partner_id", "=", f"{customer_name} ({customer_phone_no})"], ["state", "=", "draft"]]], {'fields': ['id']},
    )
    for sale_order in sale_orders:
        modelResults = models.execute_kw(database, uid, password,
            'sale.order', 'write',
            [[int(sale_order['id'])], {"state": "cancel"}],
        )
    CartItem.query.filter_by(customer_id=customer_id).delete()
    db.session.commit()

    return (json.dumps({'message': 'success'}), 200, {'ContentType': 'application/json'})