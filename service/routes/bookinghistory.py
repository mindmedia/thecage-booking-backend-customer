from service.models import (
    PurchaseLog,
    PurchaseItem,
    Pitch,
    Product,
    Field,
    Venue,
    purchase_log_schema,
    purchase_logs_schema,
    purchase_log2_schema,
    purchase_log2s_schema,
    purchase_item_schema,
    purchase_items_schema,
)
from flask import request, jsonify
from service import app
from datetime import datetime
from service import db
import jwt


@app.route("/bookinghistory", methods=["GET"])
def get_bookinghistory():
    tokenstr = request.headers["Authorization"]
    current_purchase_log_id = -1
    timestamp_now = datetime.now()
    purchaselog_ids = []
    purchaseitem_logids = []
    return_list = []

    file = open("instance/key.key", "rb")
    key = file.read()
    file.close()
    tokenstr = tokenstr.split(" ")
    token = tokenstr[1]
    customer_id = jwt.decode(token, key, algorithms=['HS256'])["customer_id"]

    purchase_log = (
        PurchaseLog.query.order_by(PurchaseLog.timestamp.desc())
        .filter_by(customer_id=customer_id)
        .all()
    )
    results_purchase_log = purchase_log2s_schema.dump(purchase_log)
    for result in purchase_log:
        purchaselog_ids.append(result.id)

    for log_id in purchaselog_ids:
        purchase_item = (
            PurchaseItem.query.order_by(PurchaseItem.id.desc())
            .filter_by(purchase_log_id=log_id)
            .filter(PurchaseItem.end_time > timestamp_now)
            .all()
        )
        results_purchase_item = purchase_items_schema.dump(purchase_item)
        for i in results_purchase_item:
        #     current_purchase_log_id = result.purchase_log_id
        #     if current_purchase_log_id not in purchaseitem_logids:
        #         purchase_log = (
        #             PurchaseLog.query.order_by(PurchaseLog.timestamp.desc())
        #             .filter_by(customer_id=customer_id, id=current_purchase_log_id)
        #             .all()
        #         )
        #         results_purchase_log = purchase_log2s_schema.dump(purchase_log)
        #         for log in results_purchase_log:
        #             log.setdefault('details', [])
        #             for i in results_purchase_item:

            pitch = Pitch.query.get(i['pitch_id'])
            i['pitchName'] = pitch.name

            field = Field.query.get(i['field_id'])
            i['fieldType'] = field.field_type
            a = field.venue_id
            venue = Venue.query.get(a)
            i['venueName'] = venue.name

            product = Product.query.get(i['product_id'])
            i['productName'] = product.name

            i['endTime'] = i.pop('end_time')
            i.pop('field_id')
            i.pop('pitch_id')
            i.pop('product_id')
            i['purchaseLogId'] = i.pop('purchase_log_id')
            i['startTime'] = i.pop('start_time')
            i['discountAmount'] = i.pop('price')
            i['amount'] = i.pop('original_price')

        #                 log['details'].append(i)
        #             return_list.append(log)
        #         purchaseitem_logids.append(result.purchase_log_id)
        return (jsonify(results_purchase_item))

    return jsonify(return_list)
