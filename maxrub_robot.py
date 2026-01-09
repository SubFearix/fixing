import requests
import time
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class MarketState:
    """Состояние рынка для конкретной пары"""
    pair_id: int
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    bid_volume:  Decimal = Decimal('0')
    ask_volume: Decimal = Decimal('0')
    mid_price: Optional[Decimal] = None
    spread: Optional[Decimal] = None
    spread_percent: Optional[Decimal] = None


@dataclass
class Position:
    """Позиция по активу"""
    lot_id: int
    quantity: Decimal
    target_quantity: Decimal


class SmartBot:
    """
    Market Maker робот с полноценной стратегией:
    - Двусторонние котировки (bid + ask)
    - Управление инвентарём
    - Динамический спред
    - Отмена устаревших ордеров
    """

    def __init__(
            self,
            api_url: str,
            user_key: str,
            target_lot_name: str = "RUB",
            check_interval: float = 3.0,
            min_profit: float = 0.5,
            base_spread_percent: float = 2.0,
            max_position_skew: float = 0.3,
            order_size_percent: float = 5.0,
            max_open_orders: int = 10,
            order_ttl_seconds: float = 30.0,
    ):
        self.api_url = api_url. rstrip('/')
        self.user_key = user_key
        self.target_lot_name = target_lot_name
        self.check_interval = check_interval
        self.min_profit = Decimal(str(min_profit / 100))
        self.base_spread_percent = Decimal(str(base_spread_percent / 100))
        self.max_position_skew = Decimal(str(max_position_skew))
        self.order_size_percent = Decimal(str(order_size_percent / 100))
        self.max_open_orders = max_open_orders
        self.order_ttl_seconds = order_ttl_seconds

        self.headers = {'X-USER-KEY': user_key, 'Content-Type': 'application/json'}

        # Данные
        self.target_lot_id:  Optional[int] = None
        self. lots: Dict[int, str] = {}
        self.lot_names_to_ids: Dict[str, int] = {}
        self.pairs: Dict[int, Dict] = {}
        self.initial_balance: List[Dict] = []

        # Статистика
        self.trades_count = 0
        self.orders_placed = 0
        self.orders_cancelled = 0
        self.total_profit = Decimal('0')

        # Отслеживание своих ордеров (order_id -> timestamp создания)
        self.my_orders: Dict[int, float] = {}

        # История цен для расчёта волатильности
        self.price_history: Dict[int, List[Decimal]] = defaultdict(list)
        self.max_price_history = 50

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    @staticmethod
    def _fmt(value, decimals:  int = 2) -> str:
        """Безопасное форматирование Decimal/float"""
        try:
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError, InvalidOperation):
            return str(value)

    @staticmethod
    def _fmt_sign(value, decimals: int = 2) -> str:
        """Форматирование со знаком"""
        try:
            v = float(value)
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:. {decimals}f}"
        except (ValueError, TypeError, InvalidOperation):
            return str(value)

    # ==================== API МЕТОДЫ ====================

    def _api_get(self, endpoint:  str, use_auth: bool = False) -> Optional[List]:
        """GET запрос к API"""
        try:
            headers = self.headers if use_auth else {}
            response = requests.get(f'{self.api_url}/{endpoint}', headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
                return []
            return None
        except Exception as e:
            print(f"[ERROR] GET /{endpoint}: {e}")
            return None

    def _api_post(self, endpoint: str, data:  dict) -> Optional[dict]:
        """POST запрос к API"""
        try:
            response = requests.post(
                f'{self. api_url}/{endpoint}',
                headers=self.headers,
                json=data,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[WARN] POST /{endpoint} failed: {response. status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"[ERROR] POST /{endpoint}:  {e}")
            return None

    def _api_delete(self, endpoint: str) -> bool:
        """DELETE запрос к API"""
        try:
            response = requests.delete(f'{self.api_url}/{endpoint}', headers=self.headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"[ERROR] DELETE /{endpoint}: {e}")
            return False

    # ==================== ИНИЦИАЛИЗАЦИЯ ====================

    def initialize(self) -> bool:
        """Инициализация робота"""
        print("\n" + "=" * 50)
        print("    ИНИЦИАЛИЗАЦИЯ MARKET MAKER")
        print("=" * 50)

        # Загрузка валют
        lots_list = self._api_get('lot')
        if not lots_list:
            raise Exception("Не удалось получить список валют")

        for lot in lots_list:
            lot_id = lot. get('lot_id') or lot.get('lot_pk')
            lot_name = str(lot.get('name', '')).strip("'\"")
            self.lots[lot_id] = lot_name
            self.lot_names_to_ids[lot_name] = lot_id
            if lot_name == self.target_lot_name:
                self.target_lot_id = lot_id

        print(f"[OK] Загружено валют: {len(self.lots)}")
        for lot_id, name in self.lots. items():
            marker = " <- ЦЕЛЕВАЯ" if lot_id == self. target_lot_id else ""
            print(f"    {name} (ID: {lot_id}){marker}")

        if not self.target_lot_id:
            raise Exception(f"Целевая валюта '{self.target_lot_name}' не найдена!")

        # Загрузка пар
        pairs_list = self._api_get('pair')
        if not pairs_list:
            raise Exception("Не удалось получить список пар")

        for pair in pairs_list:
            pair_id = pair.get('pair_id') or pair.get('pair_pk')
            first_lot = pair.get('first_lot_id') or pair.get('first_lot')
            second_lot = pair.get('second_lot_id') or pair.get('second_lot')
            self.pairs[pair_id] = {
                'first_lot':  first_lot,
                'second_lot': second_lot,
                'name': f"{self.lots. get(first_lot, '?')}/{self.lots.get(second_lot, '?')}"
            }

        print(f"[OK] Загружено торговых пар:  {len(self. pairs)}")

        # Начальный баланс
        self.initial_balance = self. get_balance()
        initial_target = self._get_lot_balance(self.target_lot_id)
        print(f"[OK] Начальный баланс {self.target_lot_name}: {self._fmt(initial_target)}")

        print("=" * 50 + "\n")
        return True

    # ==================== ПОЛУЧЕНИЕ ДАННЫХ ====================

    def get_balance(self) -> List[Dict]:
        """Получить баланс пользователя"""
        return self._api_get('balance', use_auth=True) or []

    def _get_lot_balance(self, lot_id: int) -> Decimal:
        """Получить баланс конкретной валюты"""
        balance = self. get_balance()
        for item in balance:
            if isinstance(item, dict) and item.get('lot_id') == lot_id:
                return Decimal(str(item.get('quantity', 0)))
        return Decimal('0')

    def get_all_orders(self) -> List[Dict]:
        """Получить все ордера на бирже"""
        return self._api_get('order') or []

    def _normalize_order(self, order: dict) -> dict:
        """Нормализация ключей ордера (убираем 'order.' префикс)"""
        normalized = {}
        for key, value in order.items():
            clean_key = key. replace('order.', '') if key.startswith('order.') else key
            if clean_key == 'order_pk':
                clean_key = 'order_id'
            normalized[clean_key] = value
        return normalized

    def get_open_orders(self) -> List[Dict]:
        """Получить только открытые ордера"""
        all_orders = self. get_all_orders()
        open_orders = []
        for order in all_orders:
            if not isinstance(order, dict):
                continue
            norm = self._normalize_order(order)
            closed = norm.get('closed', '')
            if not closed or closed == '':
                open_orders.append(norm)
        return open_orders

    # ==================== АНАЛИЗ РЫНКА ====================

    def analyze_market(self, pair_id: int) -> MarketState:
        """Анализ состояния рынка для пары"""
        state = MarketState(pair_id=pair_id)

        open_orders = self. get_open_orders()
        pair_orders = [o for o in open_orders if o.get('pair_id') == pair_id]

        buy_orders = []
        sell_orders = []

        for o in pair_orders:
            try:
                price = Decimal(str(o['price']))
                quantity = Decimal(str(o['quantity']))
                if o.get('type') == 'buy':
                    buy_orders.append((price, quantity))
                elif o.get('type') == 'sell':
                    sell_orders.append((price, quantity))
            except (KeyError, InvalidOperation):
                continue

        if buy_orders:
            state.best_bid = max(price for price, _ in buy_orders)
            state.bid_volume = sum(qty for price, qty in buy_orders if price == state.best_bid)

        if sell_orders:
            state. best_ask = min(price for price, _ in sell_orders)
            state.ask_volume = sum(qty for price, qty in sell_orders if price == state. best_ask)

        if state.best_bid and state.best_ask:
            state. mid_price = (state.best_bid + state.best_ask) / 2
            state.spread = state.best_ask - state.best_bid
            if state.mid_price > 0:
                state.spread_percent = (state.spread / state.mid_price) * 100

            # Сохраняем историю цен
            self.price_history[pair_id].append(state.mid_price)
            if len(self.price_history[pair_id]) > self.max_price_history:
                self. price_history[pair_id].pop(0)

        return state

    def calculate_volatility(self, pair_id: int) -> Decimal:
        """Расчёт волатильности на основе истории цен"""
        history = self.price_history.get(pair_id, [])
        if len(history) < 5:
            return Decimal('0.02')

        avg = sum(history) / len(history)
        if avg == 0:
            return Decimal('0.02')

        variance = sum((p - avg) ** 2 for p in history) / len(history)
        std_dev = Decimal(str(float(variance) ** 0.5))
        volatility = std_dev / avg

        return max(volatility, Decimal('0.01'))

    def calculate_dynamic_spread(self, pair_id: int, position_skew: Decimal) -> Tuple[Decimal, Decimal]:
        """Расчёт дина��ического спреда"""
        volatility = self.calculate_volatility(pair_id)

        spread = self. base_spread_percent + volatility

        skew_adjustment = position_skew * Decimal('0.5')

        bid_spread = spread * (1 + skew_adjustment)
        ask_spread = spread * (1 - skew_adjustment)

        min_spread = Decimal('0.005')
        max_spread = Decimal('0.10')

        bid_spread = max(min_spread, min(bid_spread, max_spread))
        ask_spread = max(min_spread, min(ask_spread, max_spread))

        return bid_spread, ask_spread

    def calculate_position_skew(self, first_lot_id:  int, second_lot_id: int) -> Decimal:
        """Расчёт отклонения позиции от целевой"""
        first_balance = self._get_lot_balance(first_lot_id)

        initial_first = Decimal('1000')
        for b in self.initial_balance:
            if b.get('lot_id') == first_lot_id:
                initial_first = Decimal(str(b.get('quantity', 1000)))
                break

        if initial_first > 0:
            first_ratio = (first_balance - initial_first) / initial_first
        else:
            first_ratio = Decimal('0')

        return max(Decimal('-1'), min(first_ratio, Decimal('1')))

    # ==================== УПРАВЛЕНИЕ ОРДЕРАМИ ====================

    def create_order(self, pair_id: int, order_type: str, quantity: Decimal, price: Decimal) -> Optional[int]:
        """Создание ордера"""
        if quantity <= 0 or price <= 0:
            return None

        data = {
            'pair_id': pair_id,
            'type': order_type,
            'quantity': float(quantity. quantize(Decimal('0.0001'), rounding=ROUND_DOWN)),
            'price': float(price.quantize(Decimal('0.01'), rounding=ROUND_DOWN))
        }

        result = self._api_post('order', data)
        if result:
            self.orders_placed += 1
            order_id = result. get('order_id')
            if order_id:
                self.my_orders[order_id] = time.time()
            return order_id
        return None

    def cancel_order(self, order_id: int) -> bool:
        """Отмена ордера"""
        success = self._api_delete(f'order/{order_id}')
        if success:
            self.orders_cancelled += 1
            self.my_orders. pop(order_id, None)
        return success

    def cancel_stale_orders(self):
        """Отмена устаревших ордеров"""
        current_time = time.time()
        stale_orders = []

        for order_id, created_time in list(self.my_orders.items()):
            if current_time - created_time > self.order_ttl_seconds:
                stale_orders.append(order_id)

        for order_id in stale_orders:
            if self. cancel_order(order_id):
                print(f"  [X] Отменён устаревший ордер #{order_id}")

    def cancel_all_my_orders(self):
        """Отмена всех своих ордеров"""
        for order_id in list(self.my_orders.keys()):
            self.cancel_order(order_id)

    # ==================== СТРАТЕГИЯ MARKET MAKING ====================

    def execute_market_making(self, pair_id: int) -> bool:
        """Основная логика Market Making для пары"""
        pair_info = self.pairs. get(pair_id)
        if not pair_info:
            return False

        first_lot_id = pair_info['first_lot']
        second_lot_id = pair_info['second_lot']
        pair_name = pair_info['name']

        # Анализ рынка
        market = self.analyze_market(pair_id)

        # Если нет рынка - создаём начальные котировки
        if not market.mid_price:
            market.mid_price = Decimal('10. 0')
            print(f"  [{pair_name}] Нет рынка, базовая цена:  {self._fmt(market. mid_price)}")

        # Расчёт позиции
        position_skew = self.calculate_position_skew(first_lot_id, second_lot_id)

        # Динамический спред
        bid_spread, ask_spread = self.calculate_dynamic_spread(pair_id, position_skew)

        # Расчёт цен
        bid_price = market. mid_price * (1 - bid_spread)
        ask_price = market.mid_price * (1 + ask_spread)

        # Проверяем что наши цены лучше рынка
        if market.best_bid and bid_price <= market.best_bid:
            bid_price = market. best_bid + Decimal('0.01')
        if market.best_ask and ask_price >= market.best_ask:
            ask_price = market.best_ask - Decimal('0.01')

        # Проверка на инвертированный спред
        if bid_price >= ask_price:
            print(f"  [{pair_name}] Спред инвертирован, пропускаем")
            return False

        # Расчёт размера ордера
        first_balance = self._get_lot_balance(first_lot_id)
        second_balance = self._get_lot_balance(second_lot_id)

        buy_budget = second_balance * self. order_size_percent
        buy_quantity = buy_budget / bid_price if bid_price > 0 else Decimal('0')

        sell_quantity = first_balance * self.order_size_percent

        min_quantity = Decimal('0.1')

        orders_created = 0

        # Корректируем размеры на основе position skew
        skew_factor = 1 + position_skew * Decimal('0.5')
        adjusted_sell_qty = sell_quantity * skew_factor
        adjusted_buy_qty = buy_quantity * (2 - skew_factor)

        # Выставляем BUY
        if adjusted_buy_qty >= min_quantity and len(self.my_orders) < self.max_open_orders:
            order_id = self. create_order(pair_id, 'buy', adjusted_buy_qty, bid_price)
            if order_id:
                orders_created += 1
                print(f"  [{pair_name}] BUY  {self._fmt(adjusted_buy_qty, 4)} @ {self._fmt(bid_price)}")

        # Выставляем SELL
        if adjusted_sell_qty >= min_quantity and len(self.my_orders) < self.max_open_orders:
            order_id = self.create_order(pair_id, 'sell', adjusted_sell_qty, ask_price)
            if order_id:
                orders_created += 1
                print(f"  [{pair_name}] SELL {self._fmt(adjusted_sell_qty, 4)} @ {self._fmt(ask_price)}")

        return orders_created > 0

    def find_arbitrage_opportunities(self) -> List[Dict]:
        """Поиск арбитражных возможностей"""
        opportunities = []

        for pair_id, pair_info in self.pairs.items():
            market = self.analyze_market(pair_id)

            if market.spread_percent and float(market.spread_percent) > 3:
                opportunities.append({
                    'type': 'spread',
                    'pair_id': pair_id,
                    'pair_name': pair_info['name'],
                    'spread_percent': market.spread_percent,
                    'best_bid': market. best_bid,
                    'best_ask': market.best_ask
                })

        opportunities.sort(key=lambda x: float(x. get('spread_percent', 0)), reverse=True)

        return opportunities[: 3]

    # ==================== ОСНОВНОЙ ЦИКЛ ====================

    def print_status(self, iteration: int):
        """Вывод текущего статуса"""
        current_target = self._get_lot_balance(self.target_lot_id)
        initial_target = Decimal('1000')
        for b in self.initial_balance:
            if b.get('lot_id') == self.target_lot_id:
                initial_target = Decimal(str(b.get('quantity', 1000)))
                break

        profit = current_target - initial_target
        profit_pct = Decimal('0')
        if initial_target > 0:
            profit_pct = (profit / initial_target) * 100

        print(f"\n{'=' * 50}")
        print(f"  Итерация #{iteration} | {time.strftime('%H:%M:%S')}")
        print("=" * 50)
        print(f"  Баланс {self. target_lot_name}: {self._fmt(current_target)}")
        print(f"  Прибыль: {self._fmt_sign(profit)} ({self._fmt_sign(profit_pct)}%)")
        print(f"  Ордеров создано: {self. orders_placed}")
        print(f"  Ордеров отменено:  {self.orders_cancelled}")
        print(f"  Активных ордеров: {len(self.my_orders)}")
        print("=" * 50)

    def run(self):
        """Запуск робота"""
        print("\n" + "#" * 50)
        print("#  SMART MARKET MAKER BOT")
        print("#" * 50)

        try:
            self.initialize()
        except Exception as e:
            print(f"[FATAL] Ошибка инициализации: {e}")
            import traceback
            traceback.print_exc()
            return

        spread_pct = float(self.base_spread_percent) * 100
        order_pct = float(self.order_size_percent) * 100

        print("Настройки:")
        print(f"  * Базовый спред: {spread_pct:.1f}%")
        print(f"  * Размер ордера: {order_pct:. 1f}% от баланса")
        print(f"  * Макс.  ордеров: {self.max_open_orders}")
        print(f"  * TTL ордера: {self.order_ttl_seconds} сек")
        print(f"  * Интервал:  {self.check_interval} сек")
        print("\n  Нажмите Ctrl+C для остановки\n")

        iteration = 0

        try:
            while True:
                iteration += 1
                self.print_status(iteration)

                # 1. Отменяем устаревшие ордера
                print("\n[1] Проверка устаревших ордеров...")
                self.cancel_stale_orders()

                # 2. Market making на всех парах
                print("\n[2] Market Making...")
                for pair_id in self.pairs:
                    self.execute_market_making(pair_id)

                # 3. Поиск арбитражных возможностей
                print("\n[3] Поиск арбитража...")
                opportunities = self.find_arbitrage_opportunities()
                if opportunities:
                    for opp in opportunities:
                        spread_val = self._fmt(opp['spread_percent'])
                        print(f"  [! ] {opp['pair_name']}: спред {spread_val}%")
                else:
                    print("  Арбитражных возможностей не найдено")

                time.sleep(self. check_interval)

        except KeyboardInterrupt:
            print("\n\n" + "=" * 50)
            print("  ОСТАНОВКА РОБОТА")
            print("=" * 50)

            print("\nОтмена всех активных ордеров...")
            self.cancel_all_my_orders()

            final_target = self._get_lot_balance(self.target_lot_id)
            initial_target = Decimal('1000')
            for b in self.initial_balance:
                if b.get('lot_id') == self.target_lot_id:
                    initial_target = Decimal(str(b. get('quantity', 1000)))
                    break

            total_profit = final_target - initial_target
            total_profit_pct = Decimal('0')
            if initial_target > 0:
                total_profit_pct = (total_profit / initial_target) * 100

            print("\n" + "=" * 50)
            print("  ИТОГОВАЯ СТАТИСТИКА")
            print("=" * 50)
            print(f"  Начальный баланс {self.target_lot_name}: {self._fmt(initial_target)}")
            print(f"  Конечный баланс {self.target_lot_name}: {self._fmt(final_target)}")
            print(f"  Прибыль:  {self._fmt_sign(total_profit)} ({self._fmt_sign(total_profit_pct)}%)")
            print(f"  Всего ордеров создано: {self. orders_placed}")
            print(f"  Всего ордеров отменено: {self. orders_cancelled}")
            print("=" * 50 + "\n")