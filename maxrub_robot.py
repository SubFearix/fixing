import requests
import time
from decimal import Decimal

class SmartBot:
    def __init__(self, api_url, user_key, target_lot_name="RUB", check_interval=3, min_profit=0.5):
        self.api_url = api_url.rstrip('/')
        self.user_key = user_key
        self.target_lot_name = target_lot_name
        self.check_interval = check_interval
        self.min_profit = Decimal(str(min_profit / 100))
        self.headers = {'X-USER-KEY': user_key, 'Content-Type': 'application/json'}

        self.target_lot_id = None
        self.lots = {}
        self.pairs = {}
        self.initial_balance = None
        self.trades_count = 0
        self.user_id = None

    def get_user_id(self):
        if self.user_id is None:
            try:
                response = requests.get(f'{self.api_url}/user/me', headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    self.user_id = data.get('user_id')
                else:
                    print(f"Ошибка получения user_id: статус {response.status_code}")
            except Exception as e:
                print(f"Ошибка при запросе user_id: {e}")
        return self.user_id

    def initialize(self):
        print("Инициализация робота...")
        response = requests.get(f'{self.api_url}/lot')
        if response.status_code == 200:
            lots_list = response.json()
            print(f"Получено валют с сервера: {len(lots_list)}")
            for lot in lots_list:
                lot_name = lot['name'].strip("'\"")
                self.lots[lot['lot_id']] = lot_name
                print(f"  - {lot['name']} (ID: {lot['lot_id']})")
                if lot_name == self.target_lot_name:
                    self.target_lot_id = lot['lot_id']
        else:
            raise Exception(f"Не удалось получить список валют. Статус: {response.status_code}")

        if not self.target_lot_id:
            raise Exception(f"Валюта {self.target_lot_name} не найдена! Доступные валюты: {', '.join(self.lots.values())}")

        response = requests.get(f'{self.api_url}/pair')
        if response.status_code == 200:
            pairs_list = response.json()
            for pair in pairs_list:
                first_lot = pair.get('sale_lot_id') or pair.get('first_lot_id') or pair.get('first_lot')
                second_lot = pair.get('buy_lot_id') or pair.get('second_lot_id') or pair.get('second_lot')
                self.pairs[pair['pair_id']] = {
                    'first_lot':  first_lot,
                    'second_lot': second_lot
                }

        self.initial_balance = self.get_balance()
        initial_val = next((b['quantity'] for b in self.initial_balance if b['lot_id'] == self.target_lot_id), 0)
        print(f"Целевая валюта: {self.target_lot_name} (ID={self.target_lot_id})")
        print(f"Начальный баланс {self.target_lot_name}: {initial_val}")
        print(f"Загружено валют: {len(self.lots)}")
        print(f"Загружено пар: {len(self.pairs)}\n")

    def get_balance(self):
        response = requests.get(f'{self.api_url}/balance', headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            # Проверка типа данных
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Если вернулся один объект, оборачиваем в список
                return [data]
            else:
                print(f"Предупреждение: неожиданный формат баланса: {type(data)}, данные: {data}")
                return []
        return []

    def get_orders(self):
        response = requests.get(f'{self.api_url}/order')
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                print(f"Предупреждение: неожиданный формат ордеров: {type(data)}")
                return []
        return []

    def get_balance_lot(self, lot_id):
        balance = self.get_balance()
        if not balance:
            return Decimal('0')

        for item in balance:
            if not isinstance(item, dict):
                print(f"Предупреждение: элемент баланса не словарь: {type(item)}, значение: {item}")
                continue
            if item.get('lot_id') == lot_id:
                return Decimal(str(item['quantity']))
        return Decimal('0')

    def create_order(self, pair_id, order_type, quantity, price):
        data = {
            'pair_id': pair_id,
            'type':  order_type,
            'quantity': float(quantity),
            'price': float(price)
        }

        try:
            response = requests.post(f'{self.api_url}/order', headers=self.headers, json=data)
            if response.status_code == 200:
                self.trades_count += 1
                return response.json()
            return None
        except Exception as e:
            print(f"Ошибка:  {e}")
            return None

    def find_spread_opportunities(self):
        orders = self.get_orders()
        print(f"DEBUG: Всего ордеров в базе: {len(orders)}. Пример ключей: {orders[0].keys() if orders else 'пусто'}")
        if not orders:
            return None
        
        user_id = self.get_user_id()
        # Filter out own orders to enable normal trading
        open_orders = [o for o in orders if isinstance(o, dict) and not o.get('closed') and o.get('user_id') != user_id]

        for pair_id in self.pairs:
            pair_orders = [o for o in open_orders if o.get('pair_id') == pair_id]
            buy_orders = [Decimal(str(o['price'])) for o in pair_orders if o.get('type') == 'buy']
            sell_orders = [Decimal(str(o['price'])) for o in pair_orders if o.get('type') == 'sell']

            if not buy_orders or not sell_orders:
                continue
            best_buy_price = max(buy_orders)
            best_sell_price = min(sell_orders)
            spread = best_sell_price - best_buy_price
            if spread > 0:
                if (spread / best_buy_price) > 0.02:
                    return {
                        'pair_id': pair_id,
                        'best_buy': best_buy_price,
                        'best_sell': best_sell_price,
                    }
        return None

    def execute_spread_trade(self, opportunity):
        pair_id = opportunity['pair_id']
        my_buy_price = float(opportunity['best_buy']) + 0.01
        my_sell_price = float(opportunity['best_sell']) - 0.01
        val_balance = float(self.get_balance_lot(self.target_lot_id))
        quantity = (val_balance * 0.1) / my_buy_price

        print(f"\n--- MARKET MAKING ---")
        print(f"Спред рынка: {opportunity['best_buy']} <-> {opportunity['best_sell']}")
        print(f"Мы ставим: BUY {my_buy_price} | SELL {my_sell_price}")

        self.create_order(pair_id, 'buy', quantity, my_buy_price)
        self.create_order(pair_id, 'sell', quantity, my_sell_price)

    def run(self):
        print("ЗАПУСК РОБОТА:  Умный робот торгаш")
        try:
            self.initialize()
        except Exception as e:
            print(f"Ошибка инициализации: {e}")
            return

        print(f"Минимальная прибыль для сделки: {float(self.min_profit * 100):.2f}%")
        print(f"Интервал анализа: {self.check_interval} сек")
        print("Робот запущен. Нажмите Ctrl+C для остановки.")
        iteration = 0

        try:
            while True:
                iteration += 1
                current_val = float(self.get_balance_lot(self.target_lot_id))
                initial_val = float(next((b['quantity'] for b in self.initial_balance if b['lot_id'] == self.target_lot_id), 0))
                profit = current_val - initial_val
                profit_percent = (profit / initial_val * 100) if initial_val > 0 else 0

                print(f"Итерация #{iteration} | {time.strftime('%H:%M:%S')}")
                print(f"Баланс RUB: {current_val:.2f} | Прибыль: {profit:+.2f} ({profit_percent:+.2f}%)")
                print(f"Сделок выполнено: {self.trades_count}")

                spread_opp = self.find_spread_opportunities()
                if spread_opp:
                    print(f"\nНайдена спред-возможность!")
                    self.execute_spread_trade(spread_opp)
                    time.sleep(1)
                    continue

                print("Прибыльных возможностей не найдено")
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n\nРобот остановлен пользователем")
            final_val = float(self.get_balance_lot(self.target_lot_id))
            initial_val = float(next((b['quantity'] for b in self.initial_balance if b['lot_id'] == self.target_lot_id), 0))
            total_profit = final_val - initial_val
            total_profit_pct = (total_profit / initial_val * 100) if initial_val > 0 else 0

            print("ИТОГОВАЯ СТАТИСТИКА")
            print(f"Начальный баланс: {initial_val:.2f}")
            print(f"Конечный баланс:   {final_val:.2f}")
            print(f"Прибыль:               {total_profit:+.2f} ({total_profit_pct:+.2f}%)")
            print(f"Всего сделок:         {self.trades_count}")
