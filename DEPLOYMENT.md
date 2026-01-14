# Развертывание инфраструктуры биржи

## Описание

Данный проект содержит Docker-конфигурацию для развертывания инфраструктуры биржи, включающей:
- Сервер базы данных (C++)
- Приложение биржи (Python Flask) в 4 экземплярах
- Nginx reverse proxy с балансировкой нагрузки по стратегии ip-hash

## Архитектура

```
User → proxy1.endpoint (nginx:80) 
         ↓ (ip-hash balancing)
         ├─→ srv1.exchange:5000
         ├─→ srv2.exchange:5000
         ├─→ srv3.exchange:5000
         └─→ srv4.exchange:5000
               ↓
         exchange-db1:7432
```

## Компоненты

### 1. База данных (exchange-db1)
- **Dockerfile**: `Dockerfile.database`
- **Порт**: 7432
- **Технология**: C++ сервер с поддержкой SQL-подобных запросов
- **Схема**: `schema.json`

### 2. Приложение биржи (srv1-4.exchange)
- **Dockerfile**: `Dockerfile.exchange`
- **Порт**: 5000 (внутренний)
- **Технология**: Python Flask
- **Конфигурация**: `config.docker.json`
- **Количество реплик**: 4

### 3. Nginx (proxy1.endpoint)
- **Образ**: nginx:alpine
- **Порт**: 80 (внешний)
- **Конфигурация**: `nginx.conf`
- **Стратегия балансировки**: ip-hash

## Быстрый старт

### Запуск инфраструктуры

```bash
docker compose up -d
```

### Проверка статуса сервисов

```bash
docker compose ps
```

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f proxy1.endpoint
docker compose logs -f exchange-db1
docker compose logs -f srv1.exchange
```

### Остановка инфраструктуры

```bash
docker compose down
```

## API Endpoints

После запуска инфраструктура доступна на `http://localhost`

### Создание пользователя
```bash
curl -X POST http://localhost/user -H "Content-Type: application/json" -d '{"username": "test_user"}'
```

### Получение списка лотов
```bash
curl http://localhost/lot
```

### Получение торговых пар
```bash
curl http://localhost/pair
```

### Создание ордера
```bash
curl -X POST http://localhost/order \
  -H "Content-Type: application/json" \
  -H "X-USER-KEY: YOUR_KEY" \
  -d '{
    "pair_id": 1,
    "quantity": 10,
    "price": 100,
    "type": "buy"
  }'
```

### Получение баланса
```bash
curl http://localhost/balance -H "X-USER-KEY: YOUR_KEY"
```

### Получение списка ордеров
```bash
curl http://localhost/order
```

## Тестирование балансировки нагрузки

Nginx использует стратегию ip-hash, которая направляет запросы от одного IP-адреса всегда на один и тот же backend сервер. Это обеспечивает консистентность сессий.

Для проверки балансировки можно добавить в серверное приложение логирование имени хоста или использовать следующую команду:

```bash
# Выполнить несколько запросов и проверить логи разных экземпляров
for i in {1..10}; do
  curl http://localhost/lot
done

# Проверить логи каждого экземпляра
docker compose logs srv1.exchange | grep "GET /lot"
docker compose logs srv2.exchange | grep "GET /lot"
docker compose logs srv3.exchange | grep "GET /lot"
docker compose logs srv4.exchange | grep "GET /lot"
```

## Сборка образов

### База данных
```bash
docker build -f Dockerfile.database -t exchange-db .
```

### Приложение биржи
```bash
docker build -f Dockerfile.exchange -t exchange-app .
```

## Конфигурация

### Nginx (nginx.conf)
Конфигурация включает:
- Upstream с 4 backend серверами
- Стратегию балансировки ip-hash
- Proxy headers для корректной передачи информации о клиенте

### База данных (schema.json)
Схема включает таблицы:
- `lot` - торговые инструменты
- `pair` - торговые пары
- `user` - пользователи
- `user_lot` - балансы пользователей
- `order` - ордера

### Приложение биржи (config.docker.json)
- `lots`: список торговых инструментов (RUB, BTC, ETH)
- `database_ip`: адрес базы данных (exchange-db1)
- `database_port`: порт базы данных (7432)

## Устранение неполадок

### Сервисы не запускаются
```bash
# Проверить логи
docker compose logs

# Пересобрать образы
docker compose build --no-cache
```

### База данных недоступна
```bash
# Проверить состояние контейнера
docker compose ps exchange-db1

# Проверить логи базы данных
docker compose logs exchange-db1
```

### Nginx не балансирует нагрузку
```bash
# Проверить конфигурацию nginx
docker compose exec proxy1.endpoint nginx -t

# Перезагрузить nginx
docker compose restart proxy1.endpoint
```

## Масштабирование

Для изменения количества реплик биржи отредактируйте `docker-compose.yaml`:

1. Добавьте/удалите сервисы srv*.exchange
2. Обновите конфигурацию upstream в `nginx.conf`
3. Пересоздайте инфраструктуру:
```bash
docker compose down
docker compose up -d
```

## Требования

- Docker 20.10+
- Docker Compose v2.0+
- Минимум 2GB RAM
- Минимум 5GB свободного места на диске
