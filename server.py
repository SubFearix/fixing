from flask import Flask, request, jsonify
import json
from database_client import DatabaseClient
from models import Exchange

app = Flask(__name__)

with open('config.json', 'r') as f:
    config = json.load(f)

db_client = DatabaseClient(config['database_ip'], config['database_port'])
exchange = Exchange(db_client, config)

exchange.initialize()

def get_user_from_request():
    user_key = request.headers.get('X-USER-KEY')
    if not user_key:
        return None, {"error": "Missing X-USER-KEY header"}, 401

    user = exchange.get_user_by_key(user_key)
    if not user:
        return None, {"error": "Invalid user key"}, 401

    return user, None, None

@app.route('/user', methods=['POST'])
def create_user():
    try:
        data = request.get_json()

        if not data or 'username' not in data:
            return jsonify({"error": "username is required"})

        username = data['username']
        key = exchange.create_user(username)
        return jsonify({"key": key})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/order', methods=['POST'])
def create_order():
    try:
        user, error, status = get_user_from_request()
        if error:
            return jsonify(error), status

        data = request.get_json()

        required_fields = ['pair_id', 'quantity', 'price', 'type']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"{field} is required"})

        if data['type'] not in ['buy', 'sell']:
            return jsonify({"error": "type must be 'buy' or 'sell'"})

        try:
            quantity = float(data['quantity'])
            price = float(data['price'])
            if quantity <= 0 or price <= 0:
                return jsonify({"error": "quantity and price must be positive"})
        except ValueError:
            return jsonify({"error": "quantity and price must be numbers"})

        user_key = request.headers.get('X-USER-KEY')
        order_id = exchange.create_order(user_key, data['pair_id'], quantity, price, data['type'])

        if order_id:
            return jsonify({"order_id": int(order_id)})
        else:
            return jsonify({"message": "Order fully executed", "order_id": None})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/order', methods=['GET'])
def get_orders():
    try:
        orders = exchange.get_all_orders()
        result = []
        for order in orders:
            result.append({
                "order_id": int(order['order_pk']),
                "user_id": int(order['order.user_id']),
                "pair_id": int(order['order.pair_id']),
                "quantity": float(order['order.quantity']),
                "price": float(order['order.price']),
                "type": order['order.type'],
                "closed": order['order.closed']
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/order', methods=['DELETE'])
def delete_order():
    try:
        user, error, status = get_user_from_request()
        if error:
            return jsonify(error), status

        data = request.get_json()

        if not data or 'order_id' not in data:
            return jsonify({"error": "order_id is required"})

        order_id = data['order_id']
        user_key = request.headers.get('X-USER-KEY')
        exchange.delete_order(user_key, order_id)

        return jsonify({"message": "Order deleted successfully"})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/lot', methods=['GET'])
def get_lots():
    try:
        lots = exchange.get_all_lots()
        result = []
        for lot in lots:
            result.append({
                "lot_id": int(lot['lot_pk']),
                "name": lot['lot.name']
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/pair', methods=['GET'])
def get_pairs():
    try:
        pairs = exchange.get_all_pairs()
        result = []
        for pair in pairs:
            result.append({
                "pair_id": int(pair['pair_pk']),
                "sale_lot_id": int(pair['pair.first_lot_id']),
                "buy_lot_id": int(pair['pair.second_lot_id'])
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/balance', methods=['GET'])
def get_balance():
    try:
        user, error, status = get_user_from_request()
        if error:
            return jsonify(error), status
        user_key = request.headers.get('X-USER-KEY')
        balance = exchange.get_balance(user_key)

        result = []
        for item in balance:
            result.append({
                "lot_id": int(item['user_lot.lot_id']),
                "quantity": float(item['user_lot.quantity'])
            })
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    print("Starting Exchange API Server...")
    print(f"Lots: {config['lots']}")
    print(f"Database: {config['database_ip']}:{config['database_port']}")
    app.run(host='0.0.0.0', port=5000, debug=True)