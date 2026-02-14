import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Файл для хранения данных
DATA_FILE = 'coinkeeper_data.json'

# Токены из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# Инициализация OpenAI клиента
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Эмодзи для бота (бело-розовая тематика + практичные)
EMOJI = {
    'wallet': '👛',
    'money': '💵',
    'coin': '🪙',
    'chart': '📊',
    'piggy': '🐷',
    'target': '🎯',
    'calendar': '📅',
    'warning': '⚠️',
    'check': '✅',
    'cross': '❌',
    'back': '◀️',
    'next': '▶️',
    'edit': '✏️',
    'delete': '🗑️',
    'undo': '↩️',
    'plus': '➕',
    'minus': '➖',
    'star': '⭐',
    'heart': '🤍',
    'pink_heart': '🩷',
    'sparkle': '✨',
    'lightning': '⚡',
    'clock': '⏰',
    'bank': '🏦',
    'gift': '🎁',
    'rocket': '🚀',
    'fire': '🔥',
    'idea': '💡',
    'lock': '🔒',
    'unlock': '🔓',
    'stats': '📈',
    'trend_up': '📈',
    'trend_down': '📉',
    'category': '📂',
    'settings': '⚙️',
    'help': '❓',
    'info': 'ℹ️',
    'save': '💾',
    'refresh': '🔄',
    'history': '📜',
    'balance': '⚖️'
}

# Состояния для ConversationHandler
(SET_GOAL_NAME, SET_GOAL_AMOUNT, SET_GOAL_DATE, SET_GOAL_MANUAL, 
 ADD_INCOME_AMOUNT, ADD_INCOME_SOURCE, ADD_EXPENSE_AMOUNT, ADD_EXPENSE_CATEGORY,
 EDIT_OPERATION, DELETE_CONFIRM, STATS_PERIOD, AI_CHAT) = range(12)

def load_data():
    """Загрузка данных из файла"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    """Сохранение данных в файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_data(user_id):
    """Получение данных пользователя"""
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {
            'incomes': [],
            'expenses': [],
            'goals': [],
            'fixed_expenses': {
                'Аренда': 0,
                'Коммуналка': 0,
                'Подписки': 0
            },
            'balance': 0,
            'settings': {
                'categories': ['Базовые нужды (Еда, Транспорт)', 'Развлечения', 'Одежда', 'Здоровье', 'Образование', 'Другое'],
                'income_sources': ['Зарплата', 'Подработка', 'Подарок', 'Дивиденды', 'Кэшбэк', 'Другое'],
                'family_count': 1,
                'goal_contribution_percent': 0.10,
                'recommendation_mode': 'current',
                'recommendation_period': 'month',
                'notifications': {
                    'enabled': True,
                    'time': '09:00'
                }
            },
            'distribution_adjustments': {
                'savings': 0,
                'buffer': 0,
                'wants': 0
            }
        }
        save_data(data)

    user_data = data[str(user_id)]
    
    # Миграция старых данных
    if 'fixed_expenses' not in user_data:
        user_data['fixed_expenses'] = {'Аренда': 0, 'Коммуналка': 0, 'Подписки': 0}
    if 'notifications' not in user_data['settings']:
        user_data['settings']['notifications'] = {'enabled': True, 'time': '09:00'}
    if 'distribution_adjustments' not in user_data:
        user_data['distribution_adjustments'] = {'savings': 0, 'buffer': 0, 'wants': 0}

    return user_data

def update_user_data(user_id, user_data):
    """Обновление данных пользователя"""
    data = load_data()
    data[str(user_id)] = user_data
    save_data(data)

def get_period_dates(period):
    """Получение дат для периода статистики"""
    now = datetime.now()
    if period == 'week':
        start = now - timedelta(days=7)
    elif period == 'month':
        start = now - timedelta(days=30)
    elif period == 'year':
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=30)
    return start, now

def format_money(amount):
    """Форматирование суммы"""
    return f"{amount:,.2f} ₽".replace(',', ' ')

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = [
        [f"{EMOJI['sparkle']} ОБЗОР"],
        [f"{EMOJI['plus']} Доход", f"{EMOJI['minus']} Расход"],
        [f"{EMOJI['target']} Цели", f"{EMOJI['chart']} Статистика"],
        [f"{EMOJI['history']} История", f"{EMOJI['settings']} Настройки"],
        [f"{EMOJI['sparkle']} ИИ ЧАТ"],
        [f"{EMOJI['help']} Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт бота"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    welcome_text = f"""
{EMOJI['sparkle']} Добро пожаловать в CoinKeeper! {EMOJI['sparkle']}

{EMOJI['pink_heart']} Ваш личный финансовый помощник {EMOJI['pink_heart']}

{EMOJI['wallet']} Текущий баланс: {format_money(user_data['balance'])}

{EMOJI['lightning']} Бот даёт рекомендации по распределению денег, 
но реальные траты зависят только от вас!

{EMOJI['idea']} Используйте кнопки ниже для управления финансами:
    """

    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = f"""
{EMOJI['info']} *CoinKeeper - Помощь* {EMOJI['info']}

{EMOJI['plus']} *Доход* - Добавить доход с возможностью отмены
{EMOJI['minus']} *Расход* - Добавить реальный расход
{EMOJI['target']} *Цели* - Управление целями (с датами и ручным пополнением)
{EMOJI['chart']} *Статистика* - Анализ за неделю/месяц/год
{EMOJI['piggy']} *Распределение* - Рекомендации ИИ по бюджету
{EMOJI['history']} *История* - Просмотр и редактирование операций

{EMOJI['warning']} Важно: 
• Бот рекомендует, но не тратит за вас
• Реальные траты = то, что вы ввели
• Всё можно отменить или отредактировать

{EMOJI['heart']} Удачи в управлении финансами!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ==================== ДОХОДЫ ====================

async def add_income_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления дохода"""
    await update.message.reply_text(
        f"{EMOJI['plus']} Введите сумму дохода:\n"
        f"{EMOJI['back']} Отправьте /cancel для отмены",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADD_INCOME_AMOUNT

async def add_income_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение суммы дохода"""
    try:
        amount = float(update.message.text.replace(' ', '').replace(',', '.'))
        if amount <= 0:
            raise ValueError
        context.user_data['income_amount'] = amount

        user_id = update.effective_user.id
        user_data = get_user_data(user_id)
        sources = user_data['settings'].get('income_sources', ['Зарплата', 'Подработка', 'Подарок', 'Другое'])

        keyboard = [[src] for src in sources]
        keyboard.append([f"{EMOJI['back']} Назад"])

        await update.message.reply_text(
            f"{EMOJI['bank']} Выберите источник дохода:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return ADD_INCOME_SOURCE
    except ValueError:
        await update.message.reply_text(f"{EMOJI['warning']} Пожалуйста, введите корректную сумму:")
        return ADD_INCOME_AMOUNT

async def add_income_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение дохода"""
    source = update.message.text
    if source == f"{EMOJI['back']} Назад":
        await update.message.reply_text("Отменено", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    amount = context.user_data['income_amount']

    income = {
        'id': len(user_data['incomes']) + 1,
        'amount': amount,
        'source': source,
        'date': datetime.now().isoformat(),
        'type': 'income'
    }

    user_data['incomes'].append(income)
    user_data['balance'] += amount
    update_user_data(user_id, user_data)

    context.user_data['last_income_id'] = income['id']

    keyboard = [[InlineKeyboardButton(f"{EMOJI['undo']} Отменить последний доход", callback_data='undo_income')]]

    await update.message.reply_text(
        f"{EMOJI['check']} Доход добавлен!\n\n"
        f"💵 Сумма: {format_money(amount)}\n"
        f"🏦 Источник: {source}\n"
        f"{EMOJI['wallet']} Новый баланс: {format_money(user_data['balance'])}",
        reply_markup=get_main_keyboard()
    )

    await update.message.reply_text(
        f"Управление операцией:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await show_distribution_recommendation(update, context, amount)

    return ConversationHandler.END

async def undo_last_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена последнего дохода"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    last_id = context.user_data.get('last_income_id')
    if not last_id:
        await query.edit_message_text(f"{EMOJI['warning']} Нет дохода для отмены")
        return

    income = None
    for i, inc in enumerate(user_data['incomes']):
        if inc['id'] == last_id:
            income = inc
            user_data['incomes'].pop(i)
            break

    if income:
        user_data['balance'] -= income['amount']
        update_user_data(user_id, user_data)
        context.user_data['last_income_id'] = None

        await query.edit_message_text(
            f"{EMOJI['undo']} Доход отменён!\n"
            f"💵 Возвращено: {format_money(income['amount'])}\n"
            f"{EMOJI['wallet']} Баланс: {format_money(user_data['balance'])}"
        )
    else:
        await query.edit_message_text(f"{EMOJI['warning']} Доход не найден")

# ==================== РАСХОДЫ ====================

async def add_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления расхода"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    categories = user_data['settings']['categories']
    keyboard = [[cat] for cat in categories]
    keyboard.append([f"{EMOJI['back']} Назад"])

    await update.message.reply_text(
        f"{EMOJI['minus']} Выберите категорию расхода:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return ADD_EXPENSE_CATEGORY

async def add_expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор категории расхода"""
    category = update.message.text

    if category == f"{EMOJI['back']} Назад":
        await update.message.reply_text("Отменено", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    context.user_data['expense_category'] = category

    await update.message.reply_text(
        f"{EMOJI['minus']} Введите сумму расхода для категории '{category}':\n"
        f"{EMOJI['back']} /cancel для отмены",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADD_EXPENSE_AMOUNT

async def add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение расхода"""
    try:
        amount = float(update.message.text.replace(' ', '').replace(',', '.'))
        if amount <= 0:
            raise ValueError

        user_id = update.effective_user.id
        user_data = get_user_data(user_id)

        category = context.user_data['expense_category']

        expense = {
            'id': len(user_data['expenses']) + 1,
            'amount': amount,
            'category': category,
            'date': datetime.now().isoformat(),
            'type': 'expense'
        }

        user_data['expenses'].append(expense)
        user_data['balance'] -= amount
        update_user_data(user_id, user_data)

        recommendation = check_budget_recommendation(user_data, category, amount)

        message = (
            f"{EMOJI['check']} Расход добавлен!\n\n"
            f"💸 Сумма: {format_money(amount)}\n"
            f"📂 Категория: {category}\n"
            f"{EMOJI['wallet']} Остаток: {format_money(user_data['balance'])}"
        )

        if recommendation:
            message += f"\n\n{EMOJI['idea']} {recommendation}"

        await update.message.reply_text(message, reply_markup=get_main_keyboard())
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(f"{EMOJI['warning']} Введите корректную сумму:")
        return ADD_EXPENSE_AMOUNT

def check_budget_recommendation(user_data, category, amount):
    """Проверка соответствия расхода рекомендациям"""
    month_start = datetime.now() - timedelta(days=30)
    month_income = sum(inc['amount'] for inc in user_data['incomes'] 
                      if datetime.fromisoformat(inc['date']) > month_start)

    if month_income == 0:
        return None

    recommended = {
        'Еда': 0.30,
        'Транспорт': 0.10,
        'Развлечения': 0.10,
        'Одежда': 0.10,
        'Здоровье': 0.05,
        'Образование': 0.10,
        'Другое': 0.10
    }

    category_spent = sum(exp['amount'] for exp in user_data['expenses'] 
                        if exp['category'] == category 
                        and datetime.fromisoformat(exp['date']) > month_start)
    category_spent += amount

    recommended_amount = month_income * recommended.get(category, 0.10)

    if category_spent > recommended_amount:
        over = category_spent - recommended_amount
        return (f"⚠️ Вы превысили рекомендуемый бюджет на '{category}'!\n"
                f"Рекомендовано: {format_money(recommended_amount)}\n"
                f"Потрачено: {format_money(category_spent)}\n"
                f"Перерасход: {format_money(over)}")
    elif category_spent > recommended_amount * 0.8:
        return f"💡 Вы близки к лимиту по категории '{category}' (80% использовано)"

    return None

# ==================== ЦЕЛИ ====================

async def goals_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню целей"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    text = f"{EMOJI['target']} *Ваши финансовые цели:*\n\n"

    if not user_data['goals']:
        text += f"{EMOJI['info']} Пока нет целей. Создайте первую!"
    else:
        for goal in user_data['goals']:
            progress = (goal['saved'] / goal['amount']) * 100 if goal['amount'] > 0 else 0
            bar = '█' * int(progress / 10) + '░' * (10 - int(progress / 10))
            deadline = goal.get('deadline', 'Не установлена')

            text += (
                f"{EMOJI['target']} *{goal['name']}*\n"
                f"💰 Цель: {format_money(goal['amount'])}\n"
                f"💵 Накоплено: {format_money(goal['saved'])} ({progress:.1f}%)\n"
                f"📊 {bar}\n"
                f"⏰ Дедлайн: {deadline}\n"
                f"{'✅ Выполнена!' if progress >= 100 else ''}\n\n"
            )

    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['plus']} Новая цель", callback_data='new_goal')],
        [InlineKeyboardButton(f"{EMOJI['piggy']} Отложить вручную", callback_data='manual_add_goal')],
        [InlineKeyboardButton(f"{EMOJI['delete']} Удалить цель", callback_data='delete_goal')]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def new_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания цели"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        f"{EMOJI['target']} Введите название цели:\n"
        f"{EMOJI['back']} /cancel для отмены"
    )
    return SET_GOAL_NAME

async def set_goal_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка названия цели"""
    context.user_data['goal_name'] = update.message.text

    await update.message.reply_text(
        f"{EMOJI['money']} Введите сумму цели:"
    )
    return SET_GOAL_AMOUNT

async def set_goal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка суммы цели"""
    try:
        amount = float(update.message.text.replace(' ', '').replace(',', '.'))
        if amount <= 0:
            raise ValueError
        context.user_data['goal_amount'] = amount

        await update.message.reply_text(
            f"{EMOJI['calendar']} Введите дату достижения цели (ДД.ММ.ГГГГ)\n"
            f"или отправьте 'пропустить':"
        )
        return SET_GOAL_DATE
    except ValueError:
        await update.message.reply_text(f"{EMOJI['warning']} Введите корректную сумму:")
        return SET_GOAL_AMOUNT

async def set_goal_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка даты цели"""
    text = update.message.text.lower()

    if text == 'пропустить':
        deadline = 'Не установлена'
    else:
        try:
            date = datetime.strptime(text, '%d.%m.%Y')
            deadline = date.strftime('%d.%m.%Y')
        except ValueError:
            await update.message.reply_text(
                f"{EMOJI['warning']} Неверный формат. Используйте ДД.ММ.ГГГГ:"
            )
            return SET_GOAL_DATE

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    goal = {
        'id': len(user_data['goals']) + 1,
        'name': context.user_data['goal_name'],
        'amount': context.user_data['goal_amount'],
        'saved': 0,
        'deadline': deadline,
        'created': datetime.now().isoformat()
    }

    user_data['goals'].append(goal)
    update_user_data(user_id, user_data)

    await update.message.reply_text(
        f"{EMOJI['check']} Цель создана!\n\n"
        f"{EMOJI['target']} {goal['name']}\n"
        f"💰 {format_money(goal['amount'])}\n"
        f"⏰ Дедлайн: {deadline}",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def manual_add_to_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ручного пополнения цели"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    if not user_data['goals']:
        await query.edit_message_text(f"{EMOJI['warning']} Сначала создайте цель!")
        return ConversationHandler.END

    keyboard = []
    for goal in user_data['goals']:
        keyboard.append([InlineKeyboardButton(
            f"{goal['name']} ({format_money(goal['saved'])}/{format_money(goal['amount'])})", 
            callback_data=f'manual_goal_{goal[\"id\"]}'
        )])

    await query.edit_message_text(
        f"{EMOJI['piggy']} Выберите цель для пополнения:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SET_GOAL_MANUAL

async def manual_add_to_goal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор цели и ввод суммы"""
    query = update.callback_query
    await query.answer()

    goal_id = int(query.data.split('_')[2])
    context.user_data['manual_goal_id'] = goal_id

    await query.edit_message_text(
        f"{EMOJI['money']} Введите сумму для отложения:"
    )
    return SET_GOAL_MANUAL

async def manual_add_to_goal_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение ручного пополнения"""
    try:
        amount = float(update.message.text.replace(' ', '').replace(',', '.'))
        if amount <= 0:
            raise ValueError

        user_id = update.effective_user.id
        user_data = get_user_data(user_id)

        goal_id = context.user_data['manual_goal_id']
        goal = None

        for g in user_data['goals']:
            if g['id'] == goal_id:
                goal = g
                break

        if not goal:
            await update.message.reply_text(f"{EMOJI['warning']} Цель не найдена")
            return ConversationHandler.END

        if amount > user_data['balance']:
            await update.message.reply_text(
                f"{EMOJI['warning']} Недостаточно средств!\n"
                f"Баланс: {format_money(user_data['balance'])}"
            )
            return ConversationHandler.END

        goal['saved'] += amount
        user_data['balance'] -= amount

        transfer = {
            'id': len(user_data['expenses']) + 1,
            'amount': amount,
            'category': f"Цель: {goal['name']}",
            'date': datetime.now().isoformat(),
            'type': 'goal_transfer'
        }
        user_data['expenses'].append(transfer)

        update_user_data(user_id, user_data)

        progress = (goal['saved'] / goal['amount']) * 100

        await update.message.reply_text(
            f"{EMOJI['check']} Отложено!\n\n"
            f"{EMOJI['target']} {goal['name']}\n"
            f"💵 Добавлено: {format_money(amount)}\n"
            f"💰 Всего накоплено: {format_money(goal['saved'])}\n"
            f"📊 Прогресс: {progress:.1f}%\n"
            f"{EMOJI['wallet']} Остаток: {format_money(user_data['balance'])}",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(f"{EMOJI['warning']} Введите корректную сумму:")
        return SET_GOAL_MANUAL

# ==================== РАСПРЕДЕЛЕНИЕ ====================

async def show_distribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ОБЗОР и рекомендации"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    settings = user_data['settings']

    mode = settings.get('recommendation_mode', 'current')
    period = settings.get('recommendation_period', 'month')

    month_start = datetime.now() - timedelta(days=30)
    month_income = sum(inc['amount'] for inc in user_data['incomes'] 
                      if datetime.fromisoformat(inc['date']) > month_start)

    actual_expenses = defaultdict(float)
    for exp in user_data['expenses']:
        if datetime.fromisoformat(exp['date']) > month_start:
            actual_expenses[exp['category']] += exp['amount']
    total_spent = sum(actual_expenses.values())

    overview_text = f"""
{EMOJI['sparkle']} *ФИНАНСОВЫЙ ОБЗОР (30 дней)* {EMOJI['sparkle']}

{EMOJI['wallet']} *Текущий баланс:* {format_money(user_data['balance'])}
{EMOJI['trend_up']} *Доходы за месяц:* {format_money(month_income)}
{EMOJI['trend_down']} *Расходы за месяц:* {format_money(total_spent)}
{EMOJI['balance']} *Остаток:* {format_money(month_income - total_spent)}
    """

    await update.message.reply_text(overview_text, parse_mode='Markdown')

    income_amount = 0
    title_period = ""

    if mode == 'current':
        if user_data['incomes']:
            income_amount = user_data['incomes'][-1]['amount']
            title_period = "текущего дохода"
        else:
            await update.message.reply_text(f"{EMOJI['warning']} Нет данных для рекомендаций!")
            return
    elif mode == 'average':
        three_months_ago = datetime.now() - timedelta(days=90)
        recent_incomes = [inc['amount'] for inc in user_data['incomes'] 
                         if datetime.fromisoformat(inc['date']) > three_months_ago]
        if recent_incomes:
            income_amount = sum(recent_incomes) / 3
            title_period = "среднего дохода (3 мес)"
        else:
            await update.message.reply_text(f"{EMOJI['warning']} Недостаточно данных за 3 месяца!")
            return
    else:
        days = {'day': 1, 'week': 7, 'month': 30}.get(period, 30)
        start_date = datetime.now() - timedelta(days=days)
        income_amount = sum(inc['amount'] for inc in user_data['incomes'] 
                           if datetime.fromisoformat(inc['date']) > start_date)
        period_name = {'day': 'сегодня', 'week': 'неделю', 'month': 'месяц'}.get(period)
        title_period = f"доходов за {period_name}"

    if income_amount <= 0:
        await update.message.reply_text(f"{EMOJI['info']} Добавьте доходы, чтобы увидеть рекомендации.")
        return

    family_count = settings.get('family_count', 1)
    goal_percent = settings.get('goal_contribution_percent', 0.1)
    display_period_name = {'day': 'сегодня', 'week': 'неделю', 'month': 'месяц'}.get(period)

    if mode in ('average', 'current'):
        if period == 'day':
            income_amount /= 30
        elif period == 'week':
            income_amount /= 4.3

    needs_multiplier = 0.5 + (family_count - 1) * 0.1
    if needs_multiplier > 0.8:
        needs_multiplier = 0.8

    fixed_total = sum(user_data.get('fixed_expenses', {}).values())
    balance = user_data['balance']
    
    min_daily_per_person = 500
    min_total_daily = min_daily_per_person * family_count
    days_in_period = {'day': 1, 'week': 7, 'month': 30}.get(period, 30)
    total_min_needs = min_total_daily * days_in_period
    
    if income_amount >= total_min_needs:
        remaining = income_amount - total_min_needs
        
        if remaining >= fixed_total:
            remaining -= fixed_total
            fixed_covered = fixed_total
        else:
            fixed_covered = remaining
            remaining = 0
            
        savings_goal = income_amount * goal_percent
        adjustment = user_data.get('distribution_adjustments', {})
        actual_savings = savings_goal + adjustment.get('savings', 0)
        
        if remaining >= actual_savings:
            remaining -= actual_savings
        else:
            actual_savings = remaining
            remaining = 0
            
        base_buffer = remaining * 0.3
        actual_buffer = base_buffer + adjustment.get('buffer', 0)
        
        if remaining >= actual_buffer:
            remaining -= actual_buffer
        else:
            actual_buffer = remaining
            remaining = 0
            
        actual_wants = remaining + adjustment.get('wants', 0)
        daily_needs_budget = total_min_needs
        
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        expenses = [e for e in user_data['expenses'] if datetime.fromisoformat(e['date']) >= month_start]
        
        spent_by_cat = defaultdict(float)
        for e in expenses:
            spent_by_cat[e['category']] += e['amount']
            
        spent_text = "\n\n📊 *УЖЕ ПОТРАЧЕНО В ЭТОМ МЕСЯЦЕ:*"
        if spent_by_cat:
            for cat, amt in spent_by_cat.items():
                spent_text += f"\n└ {cat}: {format_money(amt)}"
        else:
            spent_text += "\n└ Трат пока нет"

        buffer_spent = spent_by_cat.get('Другое', 0) + spent_by_cat.get('Здоровье', 0)
        wants_spent = spent_by_cat.get('Развлечения', 0) + spent_by_cat.get('Одежда', 0)
        
        buffer_detail = f" (потрачено {format_money(buffer_spent)} на непредвиденное)" if buffer_spent > 0 else ""
        wants_detail = f" (потрачено {format_money(wants_spent)} на удовольствия)" if wants_spent > 0 else ""
    else:
        daily_needs_budget = income_amount
        fixed_covered = 0
        actual_savings = 0
        actual_buffer = 0
        actual_wants = 0
        spent_text = ""
        buffer_detail = ""
        wants_detail = ""

    today_budget = daily_needs_budget / days_in_period
    
    warning_text = ""
    if today_budget < min_total_daily:
        warning_text = f"\n⚠️ *КРИТИЧЕСКИ:* Ваш доход не покрывает базовый минимум ({format_money(min_total_daily)}/день)."
    elif fixed_covered < fixed_total:
        warning_text = f"\n⚠️ *Внимание:* Денег хватает на еду, но недостаточно для полной оплаты аренды."

    rec_text = f"""
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
{EMOJI['idea']} *РЕКОМЕНДАЦИИ ИИ НА {display_period_name.upper()}*
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬

*База:* {title_period}
*Баланс сейчас:* {format_money(balance)}

🛒 *БАЗОВЫЕ НУЖДЫ (ПРИОРИТЕТ 1):*
└ *СЕГОДНЯ МОЖНО ТРАТИТЬ:* {format_money(today_budget)} ⚡
└ Всего на период: {format_money(daily_needs_budget)}

🏠 *ФИКСИРОВАННЫЕ (Аренда и т.д.):*
└ Выделено: {format_money(fixed_covered)} / {format_money(fixed_total)}

🐷 *ОТЛОЖИТЬ НА ЦЕЛИ:*
└ Выделено: {format_money(actual_savings)}

🛡️ *РЕЗЕРВ (Непредвиденное):*
└ {format_money(actual_buffer)}{buffer_detail}

🎁 *НА РАЗВЛЕЧЕНИЯ И ПРОЧЕЕ:*
└ {format_money(actual_wants)}{wants_detail}
{warning_text}{spent_text}

{EMOJI['sparkle']} ИИ определил приоритеты: сначала еда, затем фиксированные расходы и цели.
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
    """

    keyboard = [
        [InlineKeyboardButton("✏️ Изменить Цели", callback_data='adj_savings'),
         InlineKeyboardButton("✏️ Изменить Резерв", callback_data='adj_buffer')],
        [InlineKeyboardButton("✏️ Изменить Развлечения", callback_data='adj_wants')],
        [InlineKeyboardButton("🤖 Режим ИИ", callback_data='set_rec_mode'),
         InlineKeyboardButton("📅 Период", callback_data='set_rec_period')],
        [InlineKeyboardButton(f"{EMOJI['refresh']} Обновить обзор", callback_data='refresh_dist')]
    ]

    await update.message.reply_text(rec_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_distribution_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE, income_amount):
    """Показать рекомендацию после добавления дохода"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    family_count = user_data['settings'].get('family_count', 1)
    goal_percent = user_data['settings'].get('goal_contribution_percent', 0.1)

    needs_multiplier = 0.5 + (family_count - 1) * 0.1
    if needs_multiplier > 0.8:
        needs_multiplier = 0.8

    needs = income_amount * needs_multiplier
    savings = income_amount * goal_percent
    wants = income_amount - needs - savings
    if wants < 0:
        wants = 0
        needs = income_amount - savings

    text = f"""
{EMOJI['sparkle']} *Рекомендация по распределению:* {EMOJI['sparkle']}

💵 Доход: {format_money(income_amount)}
👥 Расчет на {family_count} чел.

{EMOJI['lightning']} *Как распределить:*
• {EMOJI['lock']} Нужды ({needs_multiplier*100:.0f}%): {format_money(needs)}
• {EMOJI['piggy']} На цели ({goal_percent*100:.0f}%): {format_money(savings)}
• {EMOJI['gift']} Остальное: {format_money(wants)}

{EMOJI['idea']} Старайтесь откладывать {format_money(savings)} сразу на ваши цели!
    """
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())

# ==================== СТАТИСТИКА ====================

async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню статистики"""
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['calendar']} За неделю", callback_data='stats_week')],
        [InlineKeyboardButton(f"{EMOJI['calendar']} За месяц", callback_data='stats_month')],
        [InlineKeyboardButton(f"{EMOJI['calendar']} За год", callback_data='stats_year')]
    ]

    await update.message.reply_text(
        f"{EMOJI['stats']} *Выберите период статистики:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    query = update.callback_query
    await query.answer()

    period = query.data.split('_')[1]
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    start_date, end_date = get_period_dates(period)

    period_incomes = [inc for inc in user_data['incomes'] 
                      if start_date <= datetime.fromisoformat(inc['date']) <= end_date]
    period_expenses = [exp for exp in user_data['expenses'] 
                       if start_date <= datetime.fromisoformat(exp['date']) <= end_date]

    total_income = sum(inc['amount'] for inc in period_incomes)
    total_expense = sum(exp['amount'] for exp in period_expenses)

    by_category = defaultdict(float)
    for exp in period_expenses:
        by_category[exp['category']] += exp['amount']

    period_names = {'week': 'неделю', 'month': 'месяц', 'year': 'год'}

    text = f"""
{EMOJI['stats']} *Статистика за {period_names.get(period, 'период')}* {EMOJI['stats']}

{EMOJI['trend_up']} *Доходы:* {format_money(total_income)}
{EMOJI['trend_down']} *Расходы:* {format_money(total_expense)}
{EMOJI['balance']} *Баланс:* {format_money(total_income - total_expense)}

{EMOJI['chart']} *По категориям:*
"""

    sorted_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    for cat, amount in sorted_categories:
        percent = (amount / total_expense * 100) if total_expense > 0 else 0
        bar = '█' * int(percent / 5)
        text += f"\n{cat}: {format_money(amount)} ({percent:.1f}%) {bar}"

    if not sorted_categories:
        text += f"\n{EMOJI['info']} Нет расходов за этот период"

    keyboard = [[InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data='back_to_stats')]]

    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== ИСТОРИЯ ====================

async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню истории"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    all_operations = []

    for inc in user_data['incomes'][-5:]:
        all_operations.append({
            'type': 'income',
            'data': inc,
            'date': datetime.fromisoformat(inc['date'])
        })

    for exp in user_data['expenses'][-5:]:
        all_operations.append({
            'type': 'expense',
            'data': exp,
            'date': datetime.fromisoformat(exp['date'])
        })

    all_operations.sort(key=lambda x: x['date'], reverse=True)

    text = f"{EMOJI['history']} *Последние операции:*\n\n"

    for op in all_operations[:10]:
        date_str = op['date'].strftime('%d.%m %H:%M')
        if op['type'] == 'income':
            text += f"{EMOJI['plus']} {date_str} +{format_money(op['data']['amount'])} ({op['data']['source']})\n"
        else:
            text += f"{EMOJI['minus']} {date_str} -{format_money(op['data']['amount'])} ({op['data']['category']})\n"

    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['delete']} Удалить", callback_data='delete_operation')],
        [InlineKeyboardButton(f"{EMOJI['refresh']} Обновить", callback_data='refresh_history')]
    ]

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_operation_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления операции"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    keyboard = []

    for inc in user_data['incomes'][-5:]:
        keyboard.append([InlineKeyboardButton(
            f"📥 {inc['source']}: +{format_money(inc['amount'])}",
            callback_data=f"del_inc_{inc['id']}"
        )])

    for exp in user_data['expenses'][-5:]:
        keyboard.append([InlineKeyboardButton(
            f"📤 {exp['category']}: -{format_money(exp['amount'])}",
            callback_data=f"del_exp_{exp['id']}"
        )])

    keyboard.append([InlineKeyboardButton(f"{EMOJI['back']} Отмена", callback_data='cancel_delete')])

    await query.edit_message_text(
        f"{EMOJI['warning']} Выберите операцию для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DELETE_CONFIRM

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления"""
    query = update.callback_query
    await query.answer()

    if query.data == 'cancel_delete':
        await query.edit_message_text(f"{EMOJI['cross']} Отменено")
        return ConversationHandler.END

    parts = query.data.split('_')
    op_type = parts[1]
    op_id = int(parts[2])

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    if op_type == 'inc':
        for i, inc in enumerate(user_data['incomes']):
            if inc['id'] == op_id:
                user_data['balance'] -= inc['amount']
                user_data['incomes'].pop(i)
                update_user_data(user_id, user_data)
                await query.edit_message_text(
                    f"{EMOJI['check']} Доход удалён!\n"
                    f"Возвращено: {format_money(inc['amount'])}"
                )
                return ConversationHandler.END
    else:
        for i, exp in enumerate(user_data['expenses']):
            if exp['id'] == op_id:
                user_data['balance'] += exp['amount']
                user_data['expenses'].pop(i)
                update_user_data(user_id, user_data)
                await query.edit_message_text(
                    f"{EMOJI['check']} Расход удалён!\n"
                    f"Возвращено: {format_money(exp['amount'])}"
                )
                return ConversationHandler.END

    await query.edit_message_text(f"{EMOJI['warning']} Операция не найдена")
    return ConversationHandler.END

# ==================== НАСТРОЙКИ ====================

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    settings = user_data['settings']
    fixed = user_data.get('fixed_expenses', {})
    mode_names = {'current': 'На текущий доход', 'average': 'Средний за 3 мес', 'period': 'Фикс. период'}
    period_names = {'day': 'На сегодня', 'week': 'На неделю', 'month': 'На месяц'}

    text = (
        f"{EMOJI['settings']} *Настройки бота*\n\n"
        f"👥 Кол-во человек: {settings.get('family_count', 1)}\n"
        f"🎯 % на цели: {settings.get('goal_contribution_percent', 0.1) * 100:.0f}%\n"
        f"🏠 *Фикс. расходы (мес):*\n"
        f"└ Аренда: {format_money(fixed.get('Аренда', 0))}\n"
        f"└ Прочее: {format_money(fixed.get('Коммуналка', 0) + fixed.get('Подписки', 0))}\n\n"
        f"🔔 Уведомления: {'ВКЛ' if settings.get('notifications', {}).get('enabled', True) else 'ВЫКЛ'} ({settings.get('notifications', {}).get('time', '09:00')})\n"
        f"🤖 Режим рекомендаций: {mode_names.get(settings.get('recommendation_mode', 'current'))}\n"
        f"📅 Период: {period_names.get(settings.get('recommendation_period', 'month'))}\n"
    )

    keyboard = [
        [InlineKeyboardButton("🏠 Изменить Аренду", callback_data="set_fixed_rent")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="set_notif_toggle"),
         InlineKeyboardButton("⏰ Время", callback_data="set_notif_time")],
        [InlineKeyboardButton("👥 Кол-во человек", callback_data="set_family_count"), 
         InlineKeyboardButton("🎯 % на цели", callback_data="set_goal_percent")],
        [InlineKeyboardButton("🤖 Режим ИИ", callback_data="set_rec_mode"),
         InlineKeyboardButton("📅 Период ИИ", callback_data="set_rec_period")],
        [InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="main_menu")]
    ]

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def set_rec_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Текущий доход", callback_data="save_rmode_current")],
        [InlineKeyboardButton("Средний за 3 мес", callback_data="save_rmode_average")],
        [InlineKeyboardButton("Фикс. период", callback_data="save_rmode_period")],
        [InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="settings")]
    ]
    await query.edit_message_text("Выберите режим расчета рекомендаций:", reply_markup=InlineKeyboardMarkup(keyboard))

async def save_rec_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mode = query.data.split('_')[2]
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['settings']['recommendation_mode'] = mode
    update_user_data(user_id, user_data)
    await query.answer(f"Режим изменен")
    await settings_menu(update, context)

async def set_rec_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("На сегодня", callback_data="save_rperiod_day")],
        [InlineKeyboardButton("На неделю", callback_data="save_rperiod_week")],
        [InlineKeyboardButton("На месяц", callback_data="save_rperiod_month")],
        [InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="settings")]
    ]
    await query.edit_message_text("Выберите период планирования:", reply_markup=InlineKeyboardMarkup(keyboard))

async def save_rec_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    period = query.data.split('_')[2]
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['settings']['recommendation_period'] = period
    update_user_data(user_id, user_data)
    await query.answer(f"Период изменен")
    await settings_menu(update, context)

async def set_family_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for i in range(1, 6):
        keyboard.append(InlineKeyboardButton(str(i), callback_data=f"save_family_{i}"))

    rows = [keyboard[i:i+3] for i in range(0, len(keyboard), 3)]
    rows.append([InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="settings")])

    await query.edit_message_text("Выберите количество человек для расчета расходов:", reply_markup=InlineKeyboardMarkup(rows))

async def save_family_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    count = int(query.data.split('_')[2])

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['settings']['family_count'] = count
    update_user_data(user_id, user_data)

    await query.answer(f"Установлено: {count} чел.")
    await settings_menu(update, context)

async def set_goal_percent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for p in [5, 10, 15, 20, 30]:
        keyboard.append(InlineKeyboardButton(f"{p}%", callback_data=f"save_gpercent_{p}"))

    rows = [keyboard[i:i+3] for i in range(0, len(keyboard), 3)]
    rows.append([InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="settings")])

    await query.edit_message_text("Выберите процент от доходов, который хотите откладывать на цели:", reply_markup=InlineKeyboardMarkup(rows))

async def save_goal_percent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    percent = int(query.data.split('_')[2]) / 100

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['settings']['goal_contribution_percent'] = percent
    update_user_data(user_id, user_data)

    await query.answer(f"Установлено: {percent*100:.0f}%")
    await settings_menu(update, context)

# ==================== ИИ ЧАТ ====================

async def ai_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало чата с ИИ"""
    if not client:
        await update.message.reply_text(
            f"{EMOJI['warning']} ИИ чат недоступен. Добавьте OPENAI_API_KEY в переменные окружения.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
        
    await update.message.reply_text(
        f"{EMOJI['sparkle']} *Финансовый помощник ИИ* {EMOJI['sparkle']}\n\n"
        "Я помогу вам пережить критические моменты, проанализировать цены и дать советы по экономии.\n\n"
        "Напишите ваш вопрос или опишите ситуацию. Для выхода нажмите кнопку 'Назад'.",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([[f"{EMOJI['back']} Назад"]], resize_keyboard=True)
    )
    return AI_CHAT

async def ai_chat_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений в ИИ чате"""
    text = update.message.text
    if text == f"{EMOJI['back']} Назад":
        await update.message.reply_text("Чат завершен", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    balance = format_money(user_data['balance'])
    fixed = sum(user_data.get('fixed_expenses', {}).values())
    
    prompt = f"""Ты — профессиональный финансовый консультант в боте CoinKeeper. 
У пользователя текущий баланс: {balance}. 
Фиксированные расходы (аренда и т.д.): {format_money(fixed)}.

Ситуация пользователя: {text}

Дай конкретный совет, как выжить на оставшуюся сумму, что купить дешевле, как сэкономить. 
Отвечай кратко, практично и поддерживающе. Используй эмодзи."""
    
    msg = await update.message.reply_text(f"{EMOJI['clock']} Думаю...")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        await msg.edit_text(answer)
    except Exception as e:
        logger.error(f"AI Chat Error: {e}")
        await msg.edit_text("Извините, произошла ошибка при общении с ИИ. Попробуйте позже.")
    
    return AI_CHAT

# ==================== ОТМЕНА ====================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    await update.message.reply_text(
        f"{EMOJI['cross']} Операция отменена",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ==================== ОБРАБОТЧИКИ КНОПОК ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == 'new_goal':
        await new_goal_start(update, context)
    elif data == 'manual_add_goal':
        await manual_add_to_goal_start(update, context)
    elif data.startswith('manual_goal_'):
        await manual_add_to_goal_amount(update, context)
    elif data == 'undo_income':
        await undo_last_income(update, context)
    elif data.startswith('stats_'):
        await show_stats(update, context)
    elif data == 'back_to_stats':
        await stats_menu(update, context)
    elif data == 'settings':
        await settings_menu(update, context)
    elif data == 'set_family_count':
        await set_family_count_callback(update, context)
    elif data.startswith('save_family_'):
        await save_family_count(update, context)
    elif data == 'set_goal_percent':
        await set_goal_percent_callback(update, context)
    elif data.startswith('save_gpercent_'):
        await save_goal_percent(update, context)
    elif data == 'set_rec_mode':
        await set_rec_mode_callback(update, context)
    elif data.startswith('save_rmode_'):
        await save_rec_mode(update, context)
    elif data == 'set_rec_period':
        await set_rec_period_callback(update, context)
    elif data.startswith('save_rperiod_'):
        await save_rec_period(update, context)
    elif data == 'set_fixed_rent':
        await query.edit_message_text("Введите сумму ежемесячной аренды (только число):", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="settings")]]))
        context.user_data['waiting_for_rent'] = True
    elif data.startswith('adj_'):
        field = data.split('_')[1]
        context.user_data['waiting_for_adjustment'] = field
        names = {'savings': 'Цели', 'buffer': 'Резерв', 'wants': 'Развлечения'}
        await query.edit_message_text(f"Введите сумму изменения для категории '{names[field]}' (число, можно с минусом):", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="refresh_dist")]]))
    elif data == 'set_notif_toggle':
        user_id = update.effective_user.id
        user_data = get_user_data(user_id)
        if 'notifications' not in user_data['settings']:
            user_data['settings']['notifications'] = {'enabled': True, 'time': '09:00'}
        user_data['settings']['notifications']['enabled'] = not user_data['settings']['notifications']['enabled']
        update_user_data(user_id, user_data)
        await query.answer(f"Уведомления {'включены' if user_data['settings']['notifications']['enabled'] else 'выключены'}")
        await settings_menu(update, context)
    elif data == 'set_notif_time':
        keyboard = []
        times = ["08:00", "09:00", "10:00", "12:00", "18:00", "20:00", "21:00"]
        for t in times:
            keyboard.append(InlineKeyboardButton(t, callback_data=f"save_ntime_{t}"))
        rows = [keyboard[i:i+3] for i in range(0, len(keyboard), 3)]
        rows.append([InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="settings")])
        await query.edit_message_text("Выберите время для ежедневных рекомендаций:", reply_markup=InlineKeyboardMarkup(rows))
    elif data.startswith('save_ntime_'):
        time_str = data.split('_')[2]
        user_id = update.effective_user.id
        user_data = get_user_data(user_id)
        user_data['settings']['notifications']['time'] = time_str
        update_user_data(user_id, user_data)
        await query.answer(f"Время установлено на {time_str}")
        await settings_menu(update, context)
    elif data == 'delete_goal':
        await delete_goal_start(update, context)
    elif data.startswith('del_goal_'):
        await confirm_delete_goal(update, context)
    elif data == 'refresh_history':
        await history_menu(update, context)
    elif data == 'refresh_dist':
        await query.edit_message_text("Обновляю...")
    elif data == 'main_menu':
        await start(update, context)

async def delete_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления цели"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    if not user_data['goals']:
        await query.edit_message_text(f"{EMOJI['warning']} Нет целей для удаления!")
        return

    keyboard = []
    for goal in user_data['goals']:
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {goal['name']}", 
            callback_data=f'del_goal_{goal[\"id\"]}'
        )])
    keyboard.append([InlineKeyboardButton(f"{EMOJI['back']} Отмена", callback_data='settings')])

    await query.edit_message_text(
        f"{EMOJI['warning']} Выберите цель для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_delete_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления цели"""
    query = update.callback_query
    await query.answer()

    goal_id = int(query.data.split('_')[2])
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    for i, goal in enumerate(user_data['goals']):
        if goal['id'] == goal_id:
            # Возвращаем накопленные средства на баланс
            user_data['balance'] += goal['saved']
            user_data['goals'].pop(i)
            update_user_data(user_id, user_data)
            await query.edit_message_text(
                f"{EMOJI['check']} Цель удалена!\n"
                f"💵 Возвращено на баланс: {format_money(goal['saved'])}"
            )
            return

    await query.edit_message_text(f"{EMOJI['warning']} Цель не найдена")

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text

    if context.user_data.get('waiting_for_rent'):
        try:
            amount = float(text.replace(' ', '').replace(',', '.'))
            user_id = update.effective_user.id
            user_data = get_user_data(user_id)
            user_data['fixed_expenses']['Аренда'] = amount
            update_user_data(user_id, user_data)
            context.user_data['waiting_for_rent'] = False
            await update.message.reply_text(f"Сумма аренды {format_money(amount)} сохранена!", reply_markup=get_main_keyboard())
            return await settings_menu(update, context)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите число.")
            return

    if context.user_data.get('waiting_for_adjustment'):
        try:
            field = context.user_data['waiting_for_adjustment']
            amount = float(text.replace(' ', '').replace(',', '.'))
            user_id = update.effective_user.id
            user_data = get_user_data(user_id)
            if 'distribution_adjustments' not in user_data:
                user_data['distribution_adjustments'] = {'savings': 0, 'buffer': 0, 'wants': 0}
            user_data['distribution_adjustments'][field] = amount
            update_user_data(user_id, user_data)
            context.user_data['waiting_for_adjustment'] = None
            await update.message.reply_text(f"Корректировка сохранена!", reply_markup=get_main_keyboard())
            return await show_distribution(update, context)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите число.")
            return

    if text == f"{EMOJI['plus']} Доход":
        context.user_data['waiting_for_rent'] = False
        return await add_income_start(update, context)
    elif text == f"{EMOJI['minus']} Расход":
        context.user_data['waiting_for_rent'] = False
        return await add_expense_start(update, context)
    elif text == f"{EMOJI['sparkle']} ИИ ЧАТ":
        context.user_data['waiting_for_rent'] = False
        return await ai_chat_start(update, context)
    elif text == f"{EMOJI['target']} Цели":
        context.user_data['waiting_for_rent'] = False
        return await goals_menu(update, context)
    elif text == f"{EMOJI['chart']} Статистика":
        context.user_data['waiting_for_rent'] = False
        return await stats_menu(update, context)
    elif text == f"{EMOJI['sparkle']} ОБЗОР":
        context.user_data['waiting_for_rent'] = False
        return await show_distribution(update, context)
    elif text == f"{EMOJI['history']} История":
        context.user_data['waiting_for_rent'] = False
        return await history_menu(update, context)
    elif text == f"{EMOJI['help']} Помощь":
        context.user_data['waiting_for_rent'] = False
        return await help_command(update, context)
    elif text == f"{EMOJI['settings']} Настройки":
        context.user_data['waiting_for_rent'] = False
        return await settings_menu(update, context)
    elif text == f"{EMOJI['back']} Назад":
        context.user_data['waiting_for_rent'] = False
        return await start(update, context)

# ==================== MAIN ====================

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler для доходов
    income_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{EMOJI['plus']} Доход$"), add_income_start)],
        states={
            ADD_INCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_income_amount)],
            ADD_INCOME_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_income_source)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # ConversationHandler для расходов
    expense_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{EMOJI['minus']} Расход$"), add_expense_start)],
        states={
            ADD_EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_category)],
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_amount)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # ConversationHandler для целей
    goal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_goal_start, pattern='^new_goal$')],
        states={
            SET_GOAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_goal_name)],
            SET_GOAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_goal_amount)],
            SET_GOAL_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_goal_date)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # ConversationHandler для ручного пополнения цели
    manual_goal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(manual_add_to_goal_start, pattern='^manual_add_goal$')],
        states={
            SET_GOAL_MANUAL: [
                CallbackQueryHandler(manual_add_to_goal_amount, pattern='^manual_goal_\\d+$'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_to_goal_save)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # ConversationHandler для удаления
    delete_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_operation_start, pattern='^delete_operation$')],
        states={
            DELETE_CONFIRM: [CallbackQueryHandler(confirm_delete, pattern='^(del_inc_|del_exp_|cancel_delete)')]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # ConversationHandler для ИИ чата
    ai_chat_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{EMOJI['sparkle']} ИИ ЧАТ$"), ai_chat_start)],
        states={
            AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_handle)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Добавляем обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(income_conv)
    application.add_handler(expense_conv)
    application.add_handler(goal_conv)
    application.add_handler(manual_goal_conv)
    application.add_handler(delete_conv)
    application.add_handler(ai_chat_conv)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"{EMOJI['rocket']} Бот CoinKeeper запущен!")
    print(f"{EMOJI['info']} Нажмите Ctrl+C для остановки")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
