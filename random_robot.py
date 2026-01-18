"""
Random Trading Robot for Exchange
Places random orders once per second to emulate market fluctuations.
"""

import requests
import random
import time
import argparse

class RandomRobot:
    def __init__(self, base_url, username=None):
        self.base_url = base_url.rstrip('/')
        self.user_key = None
        self.username = username or f"random_robot_{random.randint(1000, 9999)}"
        self.pairs = []
        self.lots = []
        
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
            print(f"Loaded {len(self.lots)} lots: {[lot['name'] for lot in self.lots]}")
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
    
    def get_orders(self):
        """Get all orders."""
        response = requests.get(f"{self.base_url}/order")
        return response.json()
    
    def place_random_order(self):
        """Place a random order."""
        if not self.pairs:
            print("No pairs available")
            return None
        
        # Select random pair
        pair = random.choice(self.pairs)
        pair_id = pair["pair_id"]
        
        # Random order type
        order_type = random.choice(["buy", "sell"])
        
        # Random quantity (1 to 10)
        quantity = round(random.uniform(0.1, 5.0), 2)
        
        # Random price (0.5 to 2.0 - simulating market fluctuations)
        price = round(random.uniform(0.5, 2.0), 4)
        
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
        
        result = response.json()
        print(f"[RANDOM] {order_type.upper()} pair={pair_id} qty={quantity} price={price} -> {result}")
        return result
    
    def run(self, duration=None):
        """
        Run the robot, placing one order per second.
        
        Args:
            duration: Run for specified seconds, or indefinitely if None
        """
        print(f"\n{'='*50}")
        print("Starting Random Robot")
        print(f"{'='*50}")
        
        # Initialize
        if not self.user_key:
            if not self.create_user():
                return
        
        if not self.fetch_lots():
            return
        
        if not self.fetch_pairs():
            return
        
        print(f"\nInitial balance: {self.get_balance()}")
        print(f"\nStarting to place random orders (1 per second)...")
        print(f"{'='*50}\n")
        
        start_time = time.time()
        order_count = 0
        
        try:
            while True:
                # Place one order
                self.place_random_order()
                order_count += 1
                
                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    break
                
                # Wait 1 second before next order
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\nRobot stopped by user")
        
        print(f"\n{'='*50}")
        print(f"Random Robot finished. Orders placed: {order_count}")
        print(f"Final balance: {self.get_balance()}")
        print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Random Trading Robot")
    parser.add_argument("--url", default="http://localhost:5000", help="Exchange API URL")
    parser.add_argument("--key", help="Existing user key to use")
    parser.add_argument("--username", help="Username for new user")
    parser.add_argument("--duration", type=int, help="Run duration in seconds (default: indefinite)")
    
    args = parser.parse_args()
    
    robot = RandomRobot(args.url, args.username)
    
    if args.key:
        robot.set_user_key(args.key)
    
    robot.run(args.duration)


if __name__ == "__main__":
    main()
