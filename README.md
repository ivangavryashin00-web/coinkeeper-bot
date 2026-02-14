# CoinKeeper Bot 🤖💰

Телеграм-бот для управления личными финансами с ИИ-ассистентом.

## Функции

- 📊 **Учёт доходов и расходов** — быстрое добавление операций
- 🎯 **Финансовые цели** — отслеживание накоплений с дедлайнами
- 🤖 **ИИ-чат** — советы по экономии от OpenAI GPT
- 📈 **Статистика** — анализ за неделю/месяц/год
- ⚙️ **Настройки** — гибкая конфигурация под ваши нужды
- 🔔 **Уведомления** — ежедневные рекомендации

## Деплой на Render

### 1. Создайте Web Service

1. Зайдите на [render.com](https://render.com)
2. Создайте новый **Web Service**
3. Подключите ваш GitHub репозиторий

### 2. Настройте Environment Variables

В разделе **Environment** добавьте:

```
BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here  # опционально для ИИ-чата
```

### 3. Настройте Build & Start

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python bot.py`

### 4. Важно! Укажите версию Python

Файл `runtime.txt` уже содержит `python-3.11.8` — это решает проблему с `imghdr` в Python 3.13+.

## Локальный запуск

```bash
# 1. Клонируйте репозиторие
git clone <repo-url>
cd coinkeeper-bot

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Создайте .env файл
cp .env.example .env
# Отредактируйте .env и добавьте свои токены

# 5. Запустите бота
python bot.py
```

## Получение токенов

### Telegram Bot Token

1. Напишите [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен в `BOT_TOKEN`

### OpenAI API Key (опционально)

1. Зарегистрируйтесь на [platform.openai.com](https://platform.openai.com)
2. Создайте API ключ
3. Добавьте в `OPENAI_API_KEY`

## Структура проекта

```
coinkeeper-bot/
├── bot.py              # Основной файл бота
├── requirements.txt    # Зависимости
├── runtime.txt         # Версия Python для Render
├── Dockerfile          # Docker конфигурация
├── .env.example        # Пример переменных окружения
├── .gitignore          # Игнорируемые файлы
└── README.md           # Этот файл
```

## Исправленные ошибки

### ❌ ModuleNotFoundError: No module named 'imghdr'

**Решение**: Файл `runtime.txt` фиксирует Python 3.11.8, где `imghdr` ещё доступен.

### ❌ Отсутствует OpenAI клиент

**Решение**: Добавлен импорт `from openai import OpenAI` и инициализация клиента.

### ❌ Токен в открытом виде

**Решение**: Токен вынесен в переменные окружения через `python-dotenv`.

## Лицензия

MIT License
