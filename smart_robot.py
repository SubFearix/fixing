"""
Smart Trading Robot for Exchange
Implements trading algorithms to maximize RUB profit.
Uses market analysis and spread trading strategies.
"""

import requests
import time
import argparse
from decimal import Decimal
from collections import defaultdict


class SmartRobot:
    def __init__(self, base_url, username=None):
        self.base_url = base_url.rstrip('/')
        self.user_key = None
        self.user_id = None
        self.username = username or "smart_robot"
        self.pairs = []
        self.lots = []
        self.lot_id_to_name = {}
        self.name_to_lot_id = {}
        self.pair_info = {}  # pair_id -> {sale_lot_id, buy_lot_id}
        self.rub_lot_id = None
        self.price_history = defaultdict(list)  # pair_id -> list of prices
        self.my_open_orders = []
        
    def create_user(self):
        """Create a new user for the robot."""
        response = requests.post(
            f"{self.base_url}/user",
            json={"username": self.username}
        )
        data = response.json()
        if "key" in data:
            self.user_key = data["key"]
            print(f"Created user '{self.username}' with key: {self.user_key}")
            return True
        else:
            print(f"Error creating user: {data}")
            return False
    
    def set_user_key(self, key):
        """Set existing user key."""
        self.user_key = key
        print(f"Using existing user key: {self.user_key}")
    
    def get_headers(self):
        """Get headers with user key."""
        return {"X-USER-KEY": self.user_key}
    
    def fetch_lots(self):
        """Fetch available lots from the exchange."""
        response = requests.get(f"{self.base_url}/lot")
        data = response.json()
        if isinstance(data, list):
            self.lots = data
            for lot in self.lots:
                self.lot_id_to_name[lot['lot_id']] = lot['name']
                self.name_to_lot_id[lot['name']] = lot['lot_id']
            
            # Find RUB lot ID
            if 'RUB' in self.name_to_lot_id:
                self.rub_lot_id = self.name_to_lot_id['RUB']
            
            print(f"Loaded {len(self.lots)} lots: {self.lot_id_to_name}")
            return True
        else:
            print(f"Error fetching lots: {data}")
            return False
    
    def fetch_pairs(self):
        """Fetch available trading pairs from the exchange."""
        response = requests.get(f"{self.base_url}/pair")
        data = response.json()
        if isinstance(data, list):
            self.pairs = data
            for pair in self.pairs:
                self.pair_info[pair['pair_id']] = {
                    'sale_lot_id': pair['sale_lot_id'],
                    'buy_lot_id': pair['buy_lot_id']
                }
            print(f"Loaded {len(self.pairs)} trading pairs")
            return True
        else:
            print(f"Error fetching pairs: {data}")
            return False
    
    def get_balance(self):
        """Get current balance."""
        response = requests.get(
            f"{self.base_url}/balance",
            headers=self.get_headers()
        )
        return response.json()
    
    def get_balance_dict(self):
        """Get balance as a dictionary {lot_id: quantity}."""
        balance = self.get_balance()
        if isinstance(balance, list):
            return {item['lot_id']: Decimal(str(item['quantity'])) for item in balance}
        return {}
    
    def get_rub_balance(self):
        """Get RUB balance."""
        balance_dict = self.get_balance_dict()
        return balance_dict.get(self.rub_lot_id, Decimal('0'))
    
    def get_orders(self):
        """Get all orders."""
        response = requests.get(f"{self.base_url}/order")
        data = response.json()
        return data if isinstance(data, list) else []
    
    def get_open_orders(self):
        """Get all open orders (not closed)."""
        orders = self.get_orders()
        return [o for o in orders if not o.get('closed')]
    
    def place_order(self, pair_id, quantity, price, order_type):
        """Place an order."""
        order_data = {
            "pair_id": pair_id,
            "quantity": quantity,
            "price": price,
            "type": order_type
        }
        
        response = requests.post(
            f"{self.base_url}/order",
            json=order_data,
            headers=self.get_headers()
        )
        
        return response.json()
    
    def delete_order(self, order_id):
        """Delete an order."""
        response = requests.delete(
            f"{self.base_url}/order",
            json={"order_id": order_id},
            headers=self.get_headers()
        )
        return response.json()
    
    def analyze_market(self):
        """
        Analyze current market state.
        Returns dict with market analysis data.
        """
        orders = self.get_open_orders()
        
        analysis = {}
        for pair in self.pairs:
            pair_id = pair['pair_id']
            pair_orders = [o for o in orders if o['pair_id'] == pair_id]
            
            buy_orders = [o for o in pair_orders if o['type'] == 'buy']
            sell_orders = [o for o in pair_orders if o['type'] == 'sell']
            
            # Sort by price
            buy_orders.sort(key=lambda x: x['price'], reverse=True)
            sell_orders.sort(key=lambda x: x['price'])
            
            best_bid = buy_orders[0]['price'] if buy_orders else None
            best_ask = sell_orders[0]['price'] if sell_orders else None
            
            spread = None
            if best_bid and best_ask:
                spread = best_ask - best_bid
            
            analysis[pair_id] = {
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'buy_orders': buy_orders,
                'sell_orders': sell_orders
            }
            
            # Track price history
            if best_bid:
                self.price_history[pair_id].append(best_bid)
                # Keep only last 100 prices
                if len(self.price_history[pair_id]) > 100:
                    self.price_history[pair_id] = self.price_history[pair_id][-100:]
        
        return analysis
    
    def find_arbitrage_opportunities(self, analysis):
        """
        Find arbitrage opportunities.
        Look for price discrepancies between related pairs.
        """
        opportunities = []
        
        # For crypto-fiat pairs, look for spread trading opportunities
        for pair_id, data in analysis.items():
            if data['spread'] and data['spread'] > 0.01:  # Spread > 1%
                pair_info = self.pair_info[pair_id]
                
                # If this pair involves RUB, it's interesting
                if pair_info['buy_lot_id'] == self.rub_lot_id or pair_info['sale_lot_id'] == self.rub_lot_id:
                    opportunities.append({
                        'type': 'spread',
                        'pair_id': pair_id,
                        'spread': data['spread'],
                        'best_bid': data['best_bid'],
                        'best_ask': data['best_ask']
                    })
        
        return opportunities
    
    def execute_spread_trading(self, analysis):
        """
        Execute spread trading strategy.
        Place buy orders slightly above best bid and sell orders slightly below best ask.
        """
        balance = self.get_balance_dict()
        actions_taken = 0
        
        for pair_id, data in analysis.items():
            pair_info = self.pair_info[pair_id]
            sale_lot = pair_info['sale_lot_id']
            buy_lot = pair_info['buy_lot_id']
            
            # Get lot names for display
            sale_lot_name = self.lot_id_to_name.get(sale_lot, str(sale_lot))
            buy_lot_name = self.lot_id_to_name.get(buy_lot, str(buy_lot))
            
            # Strategy: Market making - place competitive orders
            if data['best_bid'] and data['best_ask'] and data['spread']:
                spread_percent = data['spread'] / data['best_ask'] if data['best_ask'] else 0
                
                # If spread is significant (> 5%), try to capture it
                if spread_percent > 0.05:
                    # Place buy order slightly above best bid
                    my_bid = round(data['best_bid'] * 1.01, 4)  # 1% above best bid
                    
                    # Place sell order slightly below best ask
                    my_ask = round(data['best_ask'] * 0.99, 4)  # 1% below best ask
                    
                    # Check if we have enough balance to buy
                    buy_cost = Decimal('1') * Decimal(str(my_bid))
                    if balance.get(buy_lot, Decimal('0')) >= buy_cost:
                        result = self.place_order(pair_id, 1.0, my_bid, 'buy')
                        print(f"[SMART] BUY {sale_lot_name}/{buy_lot_name} qty=1 price={my_bid} -> {result}")
                        actions_taken += 1
                    
                    # Check if we have enough balance to sell
                    if balance.get(sale_lot, Decimal('0')) >= Decimal('1'):
                        result = self.place_order(pair_id, 1.0, my_ask, 'sell')
                        print(f"[SMART] SELL {sale_lot_name}/{buy_lot_name} qty=1 price={my_ask} -> {result}")
                        actions_taken += 1
        
        return actions_taken
    
    def execute_trend_following(self, analysis):
        """
        Execute trend following strategy.
        Buy when prices are rising, sell when falling.
        Focus on maximizing RUB.
        """
        balance = self.get_balance_dict()
        actions_taken = 0
        
        for pair_id, prices in self.price_history.items():
            if len(prices) < 5:
                continue
            
            pair_info = self.pair_info.get(pair_id)
            if not pair_info:
                continue
            
            sale_lot = pair_info['sale_lot_id']
            buy_lot = pair_info['buy_lot_id']
            
            # Calculate trend (simple moving average comparison)
            recent_avg = sum(prices[-3:]) / 3
            older_avg = sum(prices[-6:-3]) / 3 if len(prices) >= 6 else recent_avg
            
            trend = (recent_avg - older_avg) / older_avg if older_avg else 0
            
            current_price = prices[-1]
            
            # If pair is X/RUB (selling X for RUB)
            if buy_lot == self.rub_lot_id:
                # Trend is up - sell crypto for RUB at good price
                if trend > 0.02 and balance.get(sale_lot, Decimal('0')) >= Decimal('1'):
                    sell_price = round(current_price * 1.02, 4)
                    result = self.place_order(pair_id, 1.0, sell_price, 'sell')
                    print(f"[SMART-TREND] SELL (rising) pair={pair_id} qty=1 price={sell_price} -> {result}")
                    actions_taken += 1
            
            # If pair is RUB/X (buying X with RUB)
            if sale_lot == self.rub_lot_id:
                # Trend is down - buy cheap crypto to sell later
                if trend < -0.02:
                    rub_balance = balance.get(self.rub_lot_id, Decimal('0'))
                    buy_price = round(current_price * 0.98, 4)
                    cost = Decimal(str(buy_price))
                    if rub_balance >= cost:
                        result = self.place_order(pair_id, 1.0, buy_price, 'buy')
                        print(f"[SMART-TREND] BUY (falling) pair={pair_id} qty=1 price={buy_price} -> {result}")
                        actions_taken += 1
        
        return actions_taken
    
    def execute_counter_random(self, analysis):
        """
        Counter the random robot's orders.
        Take advantage of random robot's unfavorable prices.
        """
        orders = self.get_open_orders()
        balance = self.get_balance_dict()
        actions_taken = 0
        
        for pair_id, data in analysis.items():
            pair_info = self.pair_info[pair_id]
            sale_lot = pair_info['sale_lot_id']
            buy_lot = pair_info['buy_lot_id']
            
            # Look for very cheap sell orders (random robot might place these)
            for sell_order in data.get('sell_orders', []):
                # If price is very low, buy it!
                if sell_order['price'] < 0.8:  # Price below 0.8 is considered cheap
                    cost = Decimal(str(sell_order['price'])) * Decimal(str(sell_order['quantity']))
                    if balance.get(buy_lot, Decimal('0')) >= cost:
                        result = self.place_order(
                            pair_id, 
                            sell_order['quantity'], 
                            sell_order['price'], 
                            'buy'
                        )
                        print(f"[SMART-COUNTER] BUY cheap offer pair={pair_id} qty={sell_order['quantity']} price={sell_order['price']} -> {result}")
                        actions_taken += 1
                        break
            
            # Look for very expensive buy orders (random robot might place these)
            for buy_order in data.get('buy_orders', []):
                # If price is very high, sell to them!
                if buy_order['price'] > 1.5:  # Price above 1.5 is considered high
                    if balance.get(sale_lot, Decimal('0')) >= Decimal(str(buy_order['quantity'])):
                        result = self.place_order(
                            pair_id,
                            buy_order['quantity'],
                            buy_order['price'],
                            'sell'
                        )
                        print(f"[SMART-COUNTER] SELL to high bidder pair={pair_id} qty={buy_order['quantity']} price={buy_order['price']} -> {result}")
                        actions_taken += 1
                        break
        
        return actions_taken
    
    def cleanup_old_orders(self):
        """Cancel orders that have been sitting too long."""
        orders = self.get_orders()
        
        # Find our open orders
        for order in orders:
            if not order.get('closed') and order.get('user_id') == self.user_id:
                # Cancel it to free up balance
                try:
                    self.delete_order(order['order_id'])
                    print(f"[SMART] Cancelled old order {order['order_id']}")
                except Exception as e:
                    pass  # Ignore errors
    
    def run_iteration(self):
        """Run one iteration of the smart trading algorithm."""
        # Analyze market
        analysis = self.analyze_market()
        
        actions = 0
        
        # Strategy 1: Counter random robot's bad prices
        actions += self.execute_counter_random(analysis)
        
        # Strategy 2: Spread trading (market making)
        if actions == 0:
            actions += self.execute_spread_trading(analysis)
        
        # Strategy 3: Trend following
        if actions == 0:
            actions += self.execute_trend_following(analysis)
        
        return actions
    
    def run(self, duration=None, interval=0.5):
        """
        Run the robot.
        
        Args:
            duration: Run for specified seconds, or indefinitely if None
            interval: Time between iterations in seconds
        """
        print(f"\n{'='*50}")
        print("Starting Smart Trading Robot")
        print(f"{'='*50}")
        
        # Initialize
        if not self.user_key:
            if not self.create_user():
                return
        
        if not self.fetch_lots():
            return
        
        if not self.fetch_pairs():
            return
        
        initial_rub = self.get_rub_balance()
        print(f"\nInitial balance: {self.get_balance()}")
        print(f"Initial RUB: {initial_rub}")
        print(f"\nStarting smart trading algorithm...")
        print(f"{'='*50}\n")
        
        start_time = time.time()
        iteration_count = 0
        
        try:
            while True:
                iteration_count += 1
                actions = self.run_iteration()
                
                # Print status every 10 iterations
                if iteration_count % 10 == 0:
                    current_rub = self.get_rub_balance()
                    profit = current_rub - initial_rub
                    print(f"\n--- Iteration {iteration_count} | RUB: {current_rub} | Profit: {profit} ---\n")
                
                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    break
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nRobot stopped by user")
        
        final_rub = self.get_rub_balance()
        profit = final_rub - initial_rub
        
        print(f"\n{'='*50}")
        print(f"Smart Robot finished. Iterations: {iteration_count}")
        print(f"Final balance: {self.get_balance()}")
        print(f"Initial RUB: {initial_rub}")
        print(f"Final RUB: {final_rub}")
        print(f"Profit: {profit} RUB")
        print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Smart Trading Robot")
    parser.add_argument("--url", default="http://localhost:5000", help="Exchange API URL")
    parser.add_argument("--key", help="Existing user key to use")
    parser.add_argument("--username", help="Username for new user")
    parser.add_argument("--duration", type=int, help="Run duration in seconds (default: indefinite)")
    parser.add_argument("--interval", type=float, default=0.5, help="Time between iterations in seconds")
    
    args = parser.parse_args()
    
    robot = SmartRobot(args.url, args.username)
    
    if args.key:
        robot.set_user_key(args.key)
    
    robot.run(args.duration, args.interval)


if __name__ == "__main__":
    main()
