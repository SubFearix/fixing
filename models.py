from decimal import Decimal
import uuid
import datetime

class Exchange:
    def __init__(self, db_client, config):
        self.db_client = db_client
        self.config = config

    def initialize(self):
        res = self.db_client.execute_select("SELECT lot.name FROM lot")
        if not res:
            for lot_name in self.config['lots']:
                self.db_client.execute_insert(f"INSERT INTO lot VALUES ('{lot_name}')")

        lots = self.db_client.execute_select("SELECT lot_pk, lot.name FROM lot")
        exist_pairs = self.db_client.execute_select("SELECT pair_pk FROM pair")

        if not exist_pairs:
            for lot1 in lots:
                for lot2 in lots:
                    if lot1['lot_pk'] != lot2['lot_pk']:
                        self.db_client.execute_insert(f"INSERT INTO pair VALUES ({lot1['lot_pk']}, {lot2['lot_pk']})")

    def create_user(self, username):
        key = uuid.uuid4().hex
        self.db_client.execute_insert(f"INSERT INTO user VALUES ('{username}', '{key}')")

        user_data = self.db_client.execute_select(f"SELECT user_pk FROM user WHERE user.key = '{key}'")
        user_id = user_data[0]['user_pk']

        lots = self.db_client.execute_select("SELECT lot_pk FROM lot")
        for lot in lots:
            lot_id = lot['lot_pk']
            self.db_client.execute_insert(f"INSERT INTO user_lot VALUES ({user_id}, {lot_id}, 1000)")
        return key

    def get_user_by_key(self, key):
        res = self.db_client.execute_select(f"SELECT user_pk FROM user WHERE user.key = '{key}'")
        if res:
            return res[0]
        return None

    def get_balance(self, key):
        user_data = self.get_user_by_key(key)
        if not user_data:
            raise Exception("Пользователь не найден")

        user_id = user_data['user_pk']
        return self.db_client.execute_select(f"SELECT user_lot.lot_id, user_lot.quantity FROM user_lot WHERE user_lot.user_id = {user_id}")

    def get_all_orders(self):
        return self.db_client.execute_select(f"SELECT order_pk, order.user_id, order.pair_id, order.quantity, order.price, order.type, order.closed FROM order")

    def get_all_lots(self):
        return self.db_client.execute_select(f'SELECT lot_pk, lot.name FROM lot')

    def get_all_pairs(self):
        return self.db_client.execute_select(f'SELECT pair_pk, pair.first_lot_id, pair.second_lot_id FROM pair')

    def create_order(self, key, pair_id, quantity, price, order_type):
        user = self.get_user_by_key(key)
        if not user:
            raise Exception("Пользователь не найден")
        user_id = user['user_pk']

        pair = self.db_client.execute_select(f'SELECT pair.first_lot_id, pair.second_lot_id FROM pair WHERE pair_pk = {pair_id}')
        if not pair:
            raise Exception("Пара не найдена")

        first_lot_id = pair[0]['pair.first_lot_id']
        second_lot_id = pair[0]['pair.second_lot_id']

        quantity = Decimal(str(quantity))
        price = Decimal(str(price))
        if order_type == "buy":
            lot_to_check = second_lot_id
            amount_needed = quantity * price
        elif order_type == "sell":
            lot_to_check = first_lot_id
            amount_needed = quantity
        else:
            raise Exception("Неверный тип ордера")

        balance = self.db_client.execute_select(f'SELECT user_lot.quantity FROM user_lot WHERE user_lot.user_id = {user_id} AND user_lot.lot_id = {lot_to_check}')
        if not balance:
            raise Exception("Недостаточно средств")

        cur_balance = Decimal(balance[0]['user_lot.quantity'])
        if cur_balance < amount_needed:
            raise Exception(f"Недостаточно средств. Нужно: {amount_needed}, доступно: {cur_balance}")

        new_balance = cur_balance - amount_needed
        self.db_client.execute_delete(f'DELETE FROM user_lot WHERE user_lot.user_id = {user_id} AND user_lot.lot_id = {lot_to_check}')
        self.db_client.execute_insert(f'INSERT INTO user_lot VALUES ({user_id}, {lot_to_check}, {str(new_balance)})')

        remain_quantity = self._match_orders(user_id, pair_id, quantity, price, order_type, first_lot_id, second_lot_id)

        if Decimal(remain_quantity) > 0:
            self.db_client.execute_insert(f"INSERT INTO order VALUES ({user_id}, {pair_id}, {remain_quantity}, {str(price)}, '{order_type}', '')")
            orders = self.db_client.execute_select(f"SELECT order_pk FROM order WHERE order.user_id = {user_id} AND order.closed = ''")
            return orders[-1]['order_pk']

        return None

    def _match_orders(self, user_id, pair_id, quantity, price, order_type, first_lot_id, second_lot_id):
        quantity = Decimal(str(quantity))
        price = Decimal(str(price))

        if order_type == "sell":
            opposite_type = "buy"
        else:
            opposite_type = "sell"

        orders = self.db_client.execute_select(f"SELECT order_pk, order.user_id, order.quantity, order.price FROM order WHERE order.pair_id = {pair_id} AND order.type = '{opposite_type}' AND order.closed = ''")
        if order_type == "buy":
            orders.sort(key=lambda x: Decimal(x['order.price']))
        else:
            orders.sort(key=lambda x: Decimal(x['order.price']), reverse=True)

        for cur_order in orders:
            cur_price = Decimal(cur_order['order.price'])
            cur_quantity = Decimal(cur_order['order.quantity'])
            cur_user_id = cur_order['order.user_id']
            cur_order_id = cur_order['order_pk']

            if cur_user_id == user_id:
                continue

            if order_type == "buy" and cur_price > price:
                continue
            if order_type == "sell" and cur_price < price:
                continue

            possible_quantity = min(quantity, cur_quantity)
            possible_price = cur_price

            self._execute_deal(user_id, cur_user_id, possible_quantity, possible_price, order_type, first_lot_id, second_lot_id)

            new_cur_quantity = cur_quantity - possible_quantity
            if new_cur_quantity == 0:
                self._close_order(cur_order_id)
            else:
                self._update_order_quantity(cur_order_id, str(new_cur_quantity))

            quantity -= possible_quantity

            if quantity == 0:
                break

        return str(quantity)

    def _execute_deal(self, buyer_id, seller_id, quantity, price, order_type, first_lot_id, second_lot_id):
        quantity = Decimal(str(quantity))
        price = Decimal(str(price))
        total_cost = quantity * price

        if order_type == "buy":
            actual_buyer = buyer_id
            actual_seller = seller_id
        else:
            actual_buyer = seller_id
            actual_seller = buyer_id

        self._update_balance(actual_buyer, first_lot_id, quantity, add=True)
        self._update_balance(actual_seller, second_lot_id, total_cost, add=True)

    def _update_balance(self, user_id, lot_id, amount, add=True):
        result = self.db_client.execute_select(f'SELECT user_lot.quantity FROM user_lot WHERE user_lot.user_id = {user_id} AND user_lot.lot_id = {lot_id}')

        if not result:
            current = Decimal("0")
        else:
            current = Decimal(result[0]['user_lot.quantity'])

        if add:
            new_balance = current + Decimal(str(amount))
        else:
            new_balance = current - Decimal(str(amount))

        self.db_client.execute_delete(f'DELETE FROM user_lot WHERE user_lot.user_id = {user_id} AND user_lot.lot_id = {lot_id}')
        self.db_client.execute_insert(f'INSERT INTO user_lot VALUES ({user_id}, {lot_id}, {str(new_balance)})')

    def _close_order(self, order_id):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        order_data = self.db_client.execute_select(f'SELECT order.user_id, order.pair_id, order.quantity, order.price, order.type FROM order WHERE order_pk = {order_id}')

        if not order_data:
            return

        order = order_data[0]

        self.db_client.execute_delete(f'DELETE FROM order WHERE order_pk = {order_id}')

        self.db_client.execute_insert(f"INSERT INTO order VALUES ({order['order.user_id']}, {order['order.pair_id']}, {order['order.quantity']}, {order['order.price']}, '{order['order.type']}', '{timestamp}')")

    def _update_order_quantity(self, order_id, new_quantity):
        order_data = self.db_client.execute_select(f'SELECT order.user_id, order.pair_id, order.price, order.type, order.closed FROM order WHERE order_pk = {order_id}')

        if not order_data:
            return

        order = order_data[0]
        self.db_client.execute_delete(f'DELETE FROM order WHERE order_pk = {order_id}')
        self.db_client.execute_insert(f"INSERT INTO order VALUES ({order['order.user_id']}, {order['order.pair_id']}, {new_quantity}, {order['order.price']}, '{order['order.type']}', '{order['order.closed']}')")

    def delete_order(self, key, order_id):
        user = self.get_user_by_key(key)
        if not user:
            raise Exception("Пользователь не найден")
        user_id = user['user_pk']

        order_data = self.db_client.execute_select(f'SELECT order.user_id, order.pair_id, order.quantity, order.price, order.type, order.closed FROM order WHERE order_pk = {order_id}')
        if not order_data:
            raise Exception("Ордер не найден")
        order = order_data[0]
        if order['order.user_id'] != user_id:
            raise Exception("Ордер не принадлежит пользователю")
        if order['order.closed'] != "":
            raise Exception("Ордер уже закрыт")

        pair_data = self.db_client.execute_select(f"SELECT pair.first_lot_id, pair.second_lot_id FROM pair WHERE pair_pk = {order['order.pair_id']}")
        if not pair_data:
            raise Exception("Пара не найдена")

        first_lot_id = pair_data[0]['pair.first_lot_id']
        second_lot_id = pair_data[0]['pair.second_lot_id']

        quantity = Decimal(order['order.quantity'])
        price = Decimal(order['order.price'])

        if order['order.type'] == 'buy':
            amount_to_return = quantity * price
            lot_to_return = second_lot_id
        else:
            amount_to_return = quantity
            lot_to_return = first_lot_id

        self._update_balance(user_id, lot_to_return, amount_to_return, add=True)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.db_client.execute_delete(f'DELETE FROM order WHERE order_pk = {order_id}')
        self.db_client.execute_insert(f"INSERT INTO order VALUES ({order['order.user_id']}, {order['order.pair_id']}, {order['order.quantity']}, {order['order.price']}, '{order['order.type']}', '{timestamp}')")
