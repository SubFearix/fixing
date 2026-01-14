import requests
import time
import random
import sys
import matplotlib.pyplot as plt
from datetime import datetime

class ExchangeClient:
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url
        self.api_key = None
        self.username = None

    def register(self, username):
        try:
            response = requests.post(f"{self.base_url}/user", json={"username": username})
            response.raise_for_status()
            data = response.json()
            self.api_key = data['key']
            self.username = username
            print(f"Зарегистрирован пользователь {username}")
            return True
        except Exception as e:
            print(f"Ошибка регистрации: {e}")
            return False

    def _headers(self):
        return {"X-USER-KEY": self.api_key}

    def get_lots(self):
        return requests.get(f"{self.base_url}/lot").json()

    def get_pairs(self):
        return requests.get(f"{self.base_url}/pair").json()

    def get_balance(self):
        try:
            resp = requests.get(f"{self.base_url}/balance", headers=self._headers())
            if resp.status_code != 200:
                print(f"Ошибка get_balance {resp.status_code}: {resp.text}")
                return []
            data = resp.json()
            if isinstance(data, dict) and 'error' in data:
                print(f"Ошибка get_balance: {data['error']}")
                return []
            return data
        except Exception as e:
            print(f"Ошибка get_balance: {e}")
            return []

    def get_orders(self):
        try:
            resp = requests.get(f"{self.base_url}/order")
            if resp.status_code != 200:
                print(f"Ошибка get_orders {resp.status_code}: {resp.text}")
                return []
            data = resp.json()
            if isinstance(data, dict) and 'error' in data:
                print(f"Ошибка get_orders: {data['error']}")
                return []
            return data
        except Exception as e:
            print(f"Ошибка get_orders: {e}")
            return []

    def create_order(self, pair_id, quantity, price, order_type):
        data = {
            "pair_id": pair_id,
            "quantity": quantity,
            "price": price,
            "type": order_type
        }
        try:
            resp = requests.post(f"{self.base_url}/order", json=data, headers=self._headers())
            return resp.json()
        except Exception as e:
            print(f"Ошибка создания ордера: {e}")
            return None

    def delete_order(self, order_id):
        try:
            requests.delete(f"{self.base_url}/order", json={"order_id": order_id}, headers=self._headers())
            return True
        except Exception as e:
            return False

class BaseBot:
    def __init__(self, client):
        self.client = client
        self.lot_names = {}
        self.initial_balance = {}
        self.balance_history = []
        self.start_time = None

    def _load_lot_names(self):
        try:
            lots = self.client.get_lots()
            self.lot_names = {item['lot_id']: item['name'] for item in lots}
        except Exception:
            pass

    def _get_balance_dict(self):
        raw = self.client.get_balance()
        if not isinstance(raw, list):
            print(f"Ошибка get_balance вернул не список: {raw}")
            return {}
        return {item['lot_id']: float(item['quantity']) for item in raw}

    def save_initial_state(self):
        self._load_lot_names()
        self.initial_balance = self._get_balance_dict()
        self.start_time = time.time()
        self.balance_history.append((0, self.initial_balance.copy()))

        print("\n Начальный баланс ")
        self._print_balance(self.initial_balance)

    def print_summary(self):
        print("\n\n Завершение работы. Итоги ")
        final_balance = self._get_balance_dict()
        if not final_balance:
            print("ОШИБКА: Не удалось получить финальный баланс")
            print("Начальный баланс был:")
            self._print_balance(self.initial_balance)
            return
        print(f"{'Лот':<10} | {'Было':<10} | {'Стало':<10} | {'ПРОФИТ':<10}")
        print("\n")

        all_lots = set(self.initial_balance.keys()) | set(final_balance.keys())

        for lot_id in all_lots:
            name = self.lot_names.get(lot_id, f"ID {lot_id}")
            start = self.initial_balance.get(lot_id, 0.0)
            end = final_balance.get(lot_id, 0.0)
            diff = end - start

            diff_str = f"{diff:+.2f}"
            print(f"{name:<10} | {start:<10.2f} | {end:<10.2f} | {diff_str:<10}")
        print("\n")
        self._balance_graph()

    def _balance_graph(self):
        if len(self.balance_history) < 2:
            print("\nНедостаточно данных для графика")
            return
        print("\nСтрою график колебаний баланса...")

        timestamps = [timee[0] for timee in self.balance_history]
        all_lots = set()
        for _, balances in self.balance_history:
            all_lots.update(balances.keys())

        fig, ax1 = plt.subplots(1, 1, figsize=(14, 10))
        rub_lot_id = None
        for lot_id in all_lots:
            lot_name = self.lot_names.get(lot_id, "")
            if "rub" in lot_name.lower():
                rub_lot_id = lot_id
                break

        if rub_lot_id:
            rub_values = []
            for _, balances in self.balance_history:
                rub_values.append(balances.get(rub_lot_id, 0.0))

            ax1.plot(timestamps, rub_values, color='green', marker='o', markersize=4, linewidth=2.5, label='RUB баланс')
            ax1.fill_between(timestamps, rub_values, alpha=0.3, color='green')

            initial_rub = rub_values[0]
            ax1.axhline(y=initial_rub, color='blue', linestyle='--', linewidth=2, alpha=0.7, label=f'Начальный баланс ({initial_rub:.2f})')

            final_rub = rub_values[-1]
            profit = final_rub - initial_rub
            color = 'green' if profit >= 0 else 'red'
            ax1.text(timestamps[-1], final_rub, f'{profit:+.2f}',
                     fontsize=12, fontweight='bold', color=color,
                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

            ax1.set_xlabel('Время (секунды)', fontsize=12)
            ax1.set_ylabel('RUB баланс', fontsize=12)
            ax1.set_title('График колебаний баланса RUB (абсолютные значения)', fontsize=14, fontweight='bold')
            ax1.legend(loc='best', fontsize=10)
            ax1.grid(True, alpha=0.3)
        else:
            ax1.text(0.5, 0.5, 'RUB лот не найден', ha='center', va='center', transform=ax1.transAxes, fontsize=14)

        filename = f"balance_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.tight_layout()
        plt.savefig(filename, dpi=150)
        print(f"Успех! График сохранен: {filename}")
        plt.close()

    def _record_balance(self):
        current_balance = self._get_balance_dict()
        if current_balance and self.start_time:
            difference = time.time() - self.start_time
            self.balance_history.append((difference, current_balance.copy()))

    def _print_balance(self, balance_dict):
        for lot_id, qty in balance_dict.items():
            name = self.lot_names.get(lot_id, f"ID {lot_id}")
            print(f"{name}: {qty:.2f}")

class RandomBot(BaseBot):
    def run(self):
        print(" Запуск RandomBot ")
        self.client.register(f"RandomBot_{random.randint(1000,9999)}")
        self.save_initial_state()
        pairs = self.client.get_pairs()
        if not pairs:
            print("Нет доступных торговых пар.")
            return

        try:
            while True:
                pair = random.choice(pairs)
                pair_id = pair['pair_id']
                order_type = random.choice(['buy', 'sell'])

                balances = self._get_balance_dict()
                target_lot_id = pair['buy_lot_id'] if order_type == 'buy' else pair['sale_lot_id']
                available = balances.get(target_lot_id, 0.0)
                if available <= 0:
                    time.sleep(1)
                    continue

                all_orders = self.client.get_orders()
                pair_orders = [o for o in all_orders if o['pair_id'] == pair_id and o['price'] > 0]

                if pair_orders:
                    avg_price = sum(o['price'] for o in pair_orders) / len(pair_orders)
                    price = avg_price * random.uniform(0.8, 1.2)
                else:
                    price = random.uniform(10, 100)

                if order_type == 'buy':
                    max_qty = available / price
                else:
                    max_qty = available

                quantity = max_qty * random.uniform(0.1, 0.5)
                if quantity > 0:
                    print(f"[Рандомный робот] {order_type.upper()} Pair:{pair_id} Q:{quantity:.2f} P:{price:.2f}")
                    self.client.create_order(pair_id, quantity, price, order_type)

                time.sleep(random.uniform(1, 3))

        except KeyboardInterrupt:
            print("\nОстановка пользователем...")
            self._record_balance()
        except Exception as e:
            print(f"\nОшибка: {e}")
            self._record_balance()
        finally:
            self.print_summary()

class StrategyBot(BaseBot):
    def __init__(self, client):
        super().__init__(client)
        self.my_orders = {}

    def run(self):
        print("  Запуск SmartBot  ")
        self.client.register(f"SmartBot_{random.randint(1,9)}")
        self.save_initial_state()

        lots = self.client.get_lots()
        rub_lot = next((lot for lot in lots if "rub" in lot['name'].lower()), None)
        if not rub_lot: return
        rub_id = rub_lot['lot_id']

        pairs = self.client.get_pairs()
        trading_pairs = [p for p in pairs if p['buy_lot_id'] == rub_id]
        print(f"Торгую на парах: {[p['pair_id'] for p in trading_pairs]}")

        ORDER_SIZE_RUB = 50.0
        BUY_SPREAD = 0.95
        SELL_SPREAD = 1.05

        try:
            iteration = 0
            while True:
                iteration += 1
                market_orders = self.client.get_orders()
                balances = self._get_balance_dict()

                active_orders = [o for o in market_orders if o['closed'] == '']
                closed_orders = [o for o in market_orders if o['closed'] != '']

                active_orders_map = {o['order_id']: o for o in active_orders}

                orders_to_remove = []
                for my_id, my_order_info in self.my_orders.items():
                    if my_id not in active_orders_map:
                        is_closed = any(o['order_id'] == my_id for o in closed_orders)
                        if is_closed:
                            orders_to_remove.append(my_id)
                            if my_order_info['type'] == 'buy':
                                print(f"[PROFIT] Купили {my_order_info['qty']:.4f} по {my_order_info['price']:.2f}")
                            else:
                                print(f"[PROFIT] Продали {my_order_info['qty']:.4f} по {my_order_info['price']:.2f}")
                        elif my_id not in [o['order_id'] for o in market_orders]:
                            orders_to_remove.append(my_id)

                for order_del in orders_to_remove:
                    del self.my_orders[order_del]

                for pair in trading_pairs:
                    pair_id = pair['pair_id']

                    pair_orders_active = [o for o in active_orders if o['pair_id'] == pair_id]
                    pair_orders_closed = [o for o in closed_orders if o['pair_id'] == pair_id]

                    if pair_orders_closed:
                        last_deals = pair_orders_closed[-20:] #последние 20 сделок
                        total_volume = sum(o['quantity'] for o in last_deals)
                        if total_volume > 0:
                            avg_price = sum(o['price'] * o['quantity'] for o in last_deals) / total_volume
                        else:
                            avg_price = sum(o['price'] for o in last_deals) / len(last_deals)
                    else:
                        if pair_orders_active:
                            buy_orders = [o for o in pair_orders_active if o['type'] == 'buy']
                            sell_orders = [o for o in pair_orders_active if o['type'] == 'sell']

                            best_buy = max([o['price'] for o in buy_orders], default=None)
                            best_sell = min([o['price'] for o in sell_orders], default=None)

                            if best_buy and best_sell:
                                avg_price = (best_buy + best_sell) / 2
                            elif best_buy:
                                avg_price = best_buy * 1.02
                            elif best_sell:
                                avg_price = best_sell * 0.98
                            else:
                                avg_price = 100.0
                        else:
                            avg_price = 100.0

                    my_active_in_pair = {order_id: info for order_id, info in self.my_orders.items() if info['pair_id'] == pair_id}

                    has_buy = any(info['type'] == 'buy' for info in my_active_in_pair.values()) #есть ли ордер на покупку, чтобы не дублировать
                    has_sell = any(info['type'] == 'sell' for info in my_active_in_pair.values())
                    target_buy = avg_price * BUY_SPREAD
                    target_sell = avg_price * SELL_SPREAD

                    #BUY
                    rub_bal = balances.get(rub_id, 0.0)
                    if not has_buy and rub_bal > ORDER_SIZE_RUB:
                        quantity = ORDER_SIZE_RUB / target_buy
                        if quantity > 0.001:
                            print(f"[Сделка] Buy {quantity:.4f} @ {target_buy:.2f} (mid: {avg_price:.2f})")
                            resp = self.client.create_order(pair_id, quantity, target_buy, 'buy')
                            if resp and 'order_id' in resp:
                                self.my_orders[resp['order_id']] = {
                                    'pair_id': pair_id,
                                    'type': 'buy',
                                    'price': target_buy,
                                    'qty': quantity
                                }

                    #SELL
                    asset_id = pair['sale_lot_id']
                    asset_bal = balances.get(asset_id, 0.0)
                    if not has_sell:
                        quantity_to_sell = ORDER_SIZE_RUB / target_sell
                        if asset_bal >= quantity_to_sell:
                            print(f"[Сделка] Sell {quantity_to_sell:.4f} @ {target_sell:.2f} (mid: {avg_price:.2f})")
                            resp = self.client.create_order(pair_id, quantity_to_sell, target_sell, 'sell')
                            if resp and 'order_id' in resp:
                                self.my_orders[resp['order_id']] = {
                                    'pair_id': pair_id,
                                    'type': 'sell',
                                    'price': target_sell,
                                    'qty': quantity_to_sell
                                }

                    for order_id, my_info in my_active_in_pair.items():
                        if order_id in active_orders_map:
                            order = active_orders_map[order_id]
                            ideal = avg_price * (0.95 if order['type']=='buy' else 1.05)
                            if abs(order['price'] - ideal) > (avg_price * 0.03): #устарел, не соответствует рынку
                                print(f"Отмена устаревшего: {order['price']:.2f} -> новая цель {ideal:.2f}")
                                self.client.delete_order(order_id)
                                del self.my_orders[order_id]

                if iteration % 10 == 0:
                    self._record_balance()
                    print(f"\nИтерация {iteration}")
                    current_balance = self._get_balance_dict()
                    for lot_id in current_balance:
                        name = self.lot_names.get(lot_id, f"ID{lot_id}")
                        start = self.initial_balance.get(lot_id, 0.0)
                        current = current_balance[lot_id]
                        diff = current - start
                        print(f"  {name}: {current:.2f} ({diff:+.2f})")
                    print()
                time.sleep(2)

        except KeyboardInterrupt:
            print("\nОстановка пользователем...")
            self._record_balance()
        except Exception as e:
            print(f"Error: {e}")
            self._record_balance()
        finally:
            self.cancel_all_orders()
            self.print_summary()

    def cancel_all_orders(self):
        print("Полная отмена ВСЕХ активных ордеров...")
        try:
            all_orders = self.client.get_orders()
            if not isinstance(all_orders, list):
                print(f"Ошибка get_orders не вернул список при очистке")
                return

            active_orders = [o for o in all_orders if o['closed'] == '']
            print(f"Найдено {len(active_orders)} активных ордеров.")
            for order in active_orders:
                self.client.delete_order(order['order_id'])
            time.sleep(2)
        except Exception as e:
            print(f"Ошибка при очистке: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python robots.py [random|strategy]")
        sys.exit(1)
    mode = sys.argv[1]
    client = ExchangeClient()
    if mode == "random":
        bot = RandomBot(client)
        bot.run()
    elif mode == "strategy":
        bot = StrategyBot(client)
        bot.run()
    else:
        print("Неизвестный режим.")
