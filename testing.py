import requests
import threading
import time
from random_robot import RandomBot
from maxrub_robot import SmartBot

def create_user(api_url, username):
    response = requests.post(f"{api_url}/user", json={"username": username})
    if response.status_code == 200:
        data = response.json()
        print(f"Пользователь '{username}' создан")
        print(f"Ключ: {data['key']}")
        return data['key']
    else:
        print(f"Ошибка создания пользователя: {response. text}")
        return None

def run_random_robot(api_url, user_key, robot_id, interval_range=(0.3, 0.5), spread_margin=0.15):
    print(f"Запуск Рандомного Робота #{robot_id}")
    bot = RandomBot(
        api_url=api_url,
        user_key=user_key,
        interval_range=interval_range,
        spread_margin=spread_margin
    )
    bot.run(max_orders=None, auto_config=True)
def run_smart_robot(api_url, user_key, wait_time=15):
    print("Запуск Умного Робота")

    print(f"Ожидание {wait_time} секунд для формирования рынка...\n")
    time.sleep(wait_time)
    bot = SmartBot(
        api_url=api_url,
        user_key=user_key,
        target_lot_name="RUB",
        check_interval=3,
        min_profit=1.5
    )
    bot.run()

def main():
    API_URL = "http://localhost:5000"
    NUMBER_RANDOM_ROBOTS = 5

    try:
        response = requests.get(f"{API_URL}/lot")
        if response.status_code != 200:
            print(f"\nСервер недоступен на {API_URL}")
            return
    except Exception as e:
        print(f"\nНе удалось подключиться к серверу: {e}")
        return
    print("\nСервер биржи доступен")
    print("\nСоздание пользователей...")

    random_robot_keys = []
    for i in range(NUMBER_RANDOM_ROBOTS):
        key = create_user(API_URL, f"random_bot_{i+1}")
        if not key:
            return
        random_robot_keys.append(key)

    smart_robot_key = create_user(API_URL, "smart_bot")
    if not smart_robot_key:
        return

    print(f"Запуск {NUMBER_RANDOM_ROBOTS} рандомных роботов и 1 умного робота")
    print("\nДля остановки нажмите Ctrl+C")

    threads = []
    for i, key in enumerate(random_robot_keys):
        thread = threading.Thread(
            target=run_random_robot,
            args=(API_URL, key, i+1),
            kwargs={'interval_range': (0.3, 0.8), 'spread_margin': 0.12 + (i * 0.03)},
            daemon=True
        )
        threads.append(thread)
        thread.start()
        time.sleep(0.5)

    smart_thread = threading.Thread(
        target=run_smart_robot,
        args=(API_URL, smart_robot_key),
        kwargs={'wait_time': 15},
        daemon=True
    )
    threads.append(smart_thread)
    smart_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nОстановка всех роботов...")
        print("Программа завершена.")
if __name__ == "__main__":
    main()