import requests
import random
import time
from decimal import Decimal

class RandomBot:
    def __init__(self, api_url, user_key, pairs_config=None, interval_range=(1, 5), spread_margin=0.2):
        self.api_url = api_url.rstrip('/')
        self.user_key = user_key
        self.pairs_config = pairs_config or []
        self.interval_range = interval_range
        self.spread_margin = spread_margin
        self.headers = {'X-USER-KEY': user_key, 'Content-Type': 'application/json'}
        self.order_count = 0
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

    def get_balance(self):
        response = requests.get(f'{self.api_url}/balance', headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                print(f"Предупреждение: неожиданный формат баланса: {type(data)}")
                return []
        return []

    def get_pairs(self):
        response = requests.get(f'{self.api_url}/pair')
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                print(f"Предупреждение: неожиданный формат пар: {type(data)}")
                return []
        return []

    def get_lots(self):
        response = requests.get(f'{self.api_url}/lot')
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                print(f"Предупреждение: неожиданный формат валют: {type(data)}")
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

    def create_order(self, pair_id, order_type, quantity, price):
        data = {'pair_id': pair_id,
                'type': order_type,
                'quantity': float(quantity),
                'price': float(price)}

        try:
            response = requests.post(f'{self.api_url}/order', headers=self.headers, json=data)
            if response.status_code == 200:
                self.order_count += 1
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"Ошибка создания ордера: {e}")
            return None

    def get_market_prices(self, pair_id):
        orders = self.get_orders()
        if not orders:
            return None, None

        user_id = self.get_user_id()
        pair_orders = []
        for o in orders:
            if not isinstance(o, dict):
                continue
            # Filter out own orders to avoid self-trading
            if o.get('user_id') == user_id:
                continue
            if o.get('pair_id') == pair_id and not o.get('closed'):
                pair_orders.append(o)

        if not pair_orders:
            return None, None

        buy_orders = [Decimal(str(o['price'])) for o in pair_orders if o.get('type') == 'buy']
        sell_orders = [Decimal(str(o['price'])) for o in pair_orders if o.get('type') == 'sell']

        best_buy = max(buy_orders) if buy_orders else None
        best_sell = min(sell_orders) if sell_orders else None
        return best_buy, best_sell

    def generate_random_order(self):
        if not self.pairs_config:
            return False

        pair_cfg = random.choice(self.pairs_config)
        pair_id = pair_cfg['pair_id']
        best_buy, best_sell = self.get_market_prices(pair_id)
        mid_price = random.uniform(pair_cfg['min_price'], pair_cfg['max_price'])
        if best_buy and best_sell:
            mid_price = (best_buy + best_sell) / 2
        elif best_buy:
            mid_price = best_buy
        elif best_sell:
            mid_price = best_sell
        order_type = random.choice(['buy', 'sell'])
        spread_distance = mid_price * random.uniform(0.01, 0.05)

        if order_type == 'buy':
            price = mid_price - spread_distance
            if price <= 0: price = 0.1
        else:
            price = mid_price + spread_distance

        price = round(price, 2)
        quantity = round(random.uniform(pair_cfg['min_qty'], pair_cfg['max_qty']), 4)

        print(f"Bot {self.user_key[-4:]} {order_type.upper()} | Q: {quantity} | P: {price}")
        self.create_order(pair_id, order_type, quantity, price)
        return True

    def auto_configure(self):
        pairs = self.get_pairs()
        lots = self.get_lots()
        if not pairs or not lots:
            print("Не удалось получить данные о парах и валютах")
            return False
        print(f"Найдено {len(pairs)} торговых пар")

        for pair in pairs:
            config = {
                'pair_id': pair['pair_id'],
                'min_price': 0.5,
                'max_price': 200.0,
                'min_qty': 0.1,
                'max_qty': 500.0
            }
            self.pairs_config.append(config)
        print(f"Создана конфигурация для {len(self.pairs_config)} пар")
        return True

    def run(self, max_orders=None, auto_config=True):
        print("ЗАПУСК РОБОТА:  Генератор рыночной активности")
        print(f"Интервал между ордерами: {self.interval_range[0]}-{self.interval_range[1]} сек")
        print(f"Минимальный спред: {self.spread_margin * 100:.1f}%")

        if auto_config and not self.pairs_config:
            print("\nСоздание конфигурации...")
            if not self.auto_configure():
                return

        if max_orders:
            print(f"Максимальное количество ордеров: {max_orders}")
        else:
            print("Режим непрерывной работы")
        print("Робот запущен. Нажмите Ctrl+C для остановки.")

        try:
            while True:
                if max_orders and self.order_count >= max_orders:
                    print(f"\nДостигнут лимит ордеров: {max_orders}")
                    break
                self.generate_random_order()
                pause = random.uniform(self.interval_range[0], self.interval_range[1])
                time.sleep(pause)
        except KeyboardInterrupt:
            print("\n\nРобот остановлен пользователем")
            print(f"Всего создано ордеров: {self.order_count}")