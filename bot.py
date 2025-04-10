TOKEN = "6899460382:AAG5HK59MlnZfBM6_AHhSauov_1EaFjdFeo"
DB_PATH = "test.db"
SUBSCRIPTION_DB = "subscriptions.db"
import sqlite3
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

# Укажите реальный токен бота
CHECK_INTERVAL = 86400  # время в секундах между сохранениями подписок (по умолчанию раз в день)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Глобальное хранилище состояния для показа олимпиад
user_olympiads_state = {}

# Глобальное хранилище фильтров и состояний поиска
user_filters = {}       # {chat_id: {"subject": ..., "grade": ..., "level": ...}}
user_state = {} # {chat_id: "subject" | "grade" | "level" | None}
def init_subscription_db():
    """Создает таблицу подписок в отдельной базе, если её нет."""
    conn = sqlite3.connect(SUBSCRIPTION_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Subscriptions (
            user_id INTEGER,
            olympiad_id INTEGER,
            PRIMARY KEY (user_id, olympiad_id)
        )
    """)
    conn.commit()
    conn.close()

init_subscription_db()


def get_olympiads(subject=None, level=None, sort_by_rating=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = ("SELECT id, name, level, rating, description, image_link, subjects, events, grade "
             "FROM Olympiads WHERE 1=1")
    params = []
    if subject and subject != "Любой":
        # Так как предметы хранятся как JSON-массив строк,
        # добавляем кавычки вокруг subject для точного совпадения.
        query += " AND subjects LIKE ?"
        params.append(f'%{json.dumps(subject)}%')
    if level and level != "Любой":
        if level == "Нет":
            query += " AND level IS -1"
        else:
            query += " AND level = ?"
            params.append(int(level))
    if sort_by_rating:
        query += " ORDER BY rating DESC"
    
    cursor.execute(query, params)
    olympiads = cursor.fetchall()
    conn.close()
    return olympiads

def filter_by_grade(olympiads, grade):
    """
    Фильтрует список олимпиад по классу.
    Если у олимпиады классы не указаны, она включается в результат.
    Если grade == "Любой", возвращаются все олимпиады.
    """
    try:
        grade_int = int(grade)
    except ValueError:
        return olympiads  # Если не число, возвращаем все олимпиады

    filtered = []
    for olympiad in olympiads:
        grade_field = olympiad[8]  # индекс 8 – столбец grade
        if not grade_field or grade_field in ["", "Не указаны в описании", None]:
            filtered.append(olympiad)  # Если классы не указаны, оставляем
            continue

        try:
            if isinstance(grade_field, list):
                grade_list = grade_field
            else:
                grade_list = json.loads(grade_field)

            if grade_int in grade_list:
                filtered.append(olympiad)
        except Exception:
            pass  # Если не удалось обработать JSON, просто пропускаем

    return filtered



def get_all_subjects():
    """Извлекает все уникальные предметы из базы (поле subjects хранится как JSON-массив)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT subjects FROM Olympiads")
    subjects_data = cursor.fetchall()
    conn.close()
    subjects_set = set()
    for row in subjects_data:
        try:
            subjects = json.loads(row[0])
            for s in subjects:
                subjects_set.add(s)
        except Exception:
            pass
    return list(subjects_set)

def get_all_grades():
    """Возвращает список классов (например, от 1 до 11)."""
    return [str(i) for i in range(1, 12)]

def get_all_levels():
    """Возвращает список уровней олимпиады с дополнительными опциями."""
    return ["Любой", "1", "2", "3", "Нет"]

async def send_next(chat_id: int, index: int):
    state = user_olympiads_state.get(chat_id, {})
    olympiads = state.get("olympiads", [])
    if index < len(olympiads):
        olympiad = olympiads[index]
        level_text = olympiad[2] if olympiad[2] != -1 else "Нет"
        # Обработка информации о классах
        try:
            #grade_list = json.loads(olympiad[8])
            #grade_text = ", ".join(grade_list)
            grade_text = " ". join(list(map(str,json.loads(olympiad[8]))))
        except Exception:
            grade_text = "Не указаны"
        text = (f"🏆 {olympiad[1]}\n"
                f"Уровень: {level_text}\n"
                f"Классы: {grade_text}\n"
                f"Рейтинг: {olympiad[3]}\n"
                f"ID: {olympiad[0]}\n"
                f"Описание: {olympiad[4]}\n"
                f"Предметы: {" ".join(json.loads(olympiad[6]))}\n")
        # Обработка этапов (поле events, индекс 7)
        stages_text = ""
        try:
            events = json.loads(olympiad[7])
            if events:
                stages_text = "Этапы:\n"
                for event in events:
                    name = event.get("Name", "Этап")
                    start = event.get("startDate", None)
                    end = event.get("endDate", None)
                    if start and start != -1:
                        start_str = datetime.fromtimestamp(start).strftime("%Y-%m-%d")
                    else:
                        start_str = "N/A"
                    if end and end != -1:
                        end_str = datetime.fromtimestamp(end).strftime("%Y-%m-%d")
                    else:
                        end_str = "N/A"
                    stages_text += f"{name}: {start_str} - {end_str}\n"
        except Exception:
            stages_text = "Этапы не доступны.\n"
        text += stages_text

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⬅️ Вернуться на главную")],
                [KeyboardButton(text="✅ Подписаться")],
                [KeyboardButton(text="❌ Отписаться")],
                [KeyboardButton(text="➡️ Далее")]
            ],
            resize_keyboard=True
        )
        user_olympiads_state[chat_id]["index"] = index
        if olympiad[5] and olympiad[5].strip() != "":
            try:
                await bot.send_photo(chat_id, photo=olympiad[5], caption=text, reply_markup=keyboard)
            except Exception:
                await bot.send_message(chat_id, text, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id, text, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, "Больше олимпиад не найдено.")

def send_olympiads_one_by_one(chat_id: int, olympiads: list):
    user_olympiads_state[chat_id] = {"olympiads": olympiads, "index": 0}
    asyncio.create_task(send_next(chat_id, 0))

def subscribe_user(user_id: int, olympiad_id: int):
    # Записываем подписку в отдельную базу данных
    conn = sqlite3.connect(SUBSCRIPTION_DB)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO Subscriptions (user_id, olympiad_id) VALUES (?, ?)",
        (user_id, olympiad_id)
    )
    conn.commit()
    conn.close()
    asyncio.create_task(bot.send_message(user_id, f"Вы подписались на олимпиаду {olympiad_id}"))

def unsubscribe_user(user_id: int, olympiad_id: int):
    conn = sqlite3.connect(SUBSCRIPTION_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Subscriptions WHERE user_id = ? AND olympiad_id = ?", (user_id, olympiad_id))
    conn.commit()
    conn.close()
    asyncio.create_task(bot.send_message(user_id, f"Вы отписались от олимпиады {olympiad_id}"))

def get_subscriptions(user_id: int):
    # Получаем список подписок из отдельной базы данных, затем достаем данные об олимпиадах из основной базы
    conn_sub = sqlite3.connect(SUBSCRIPTION_DB)
    cursor = conn_sub.cursor()
    cursor.execute("SELECT olympiad_id FROM Subscriptions WHERE user_id = ?", (user_id,))
    olympiad_ids = cursor.fetchall()
    conn_sub.close()
    results = []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for (oid,) in olympiad_ids:
        cursor.execute("SELECT id, name FROM Olympiads WHERE id = ?", (oid,))
        row = cursor.fetchone()
        if row:
            results.append(row)
    conn.close()
    return results

def check_notifications():
    # Выбираем подписки из отдельной базы
    conn_sub = sqlite3.connect(SUBSCRIPTION_DB)
    cursor = conn_sub.cursor()
    cursor.execute("SELECT user_id, olympiad_id FROM Subscriptions")
    subscriptions = cursor.fetchall()
    conn_sub.close()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for user_id, olympiad_id in subscriptions:
        cursor.execute("SELECT name, events FROM Olympiads WHERE id = ?", (olympiad_id,))
        result = cursor.fetchone()
        if result:
            name, events_json = result
            try:
                events = json.loads(events_json)
                today = datetime.today().strftime('%Y-%m-%d')
                for event in events:
                    start_ts = event.get("startDate", None)
                    if start_ts and start_ts != -1:
                        event_date = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')
                        if event_date == today:
                            asyncio.create_task(bot.send_message(user_id, f"🏆 Сегодня начинается этап: {event.get('Name', 'Этап')} олимпиады {name}!"))
            except Exception:
                pass
    conn.close()


# --- Обработчики поиска олимпиад с фильтрами ---

@dp.message(lambda message: message.text == "/start" or message.text == "⬅️ Вернуться на главную")
async def start_command(message: types.Message):
    user_state[message.chat.id] = ""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти олимпиады")],
            [KeyboardButton(text="📋 Мои подписки")]
        ],
        resize_keyboard=True
    )
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=keyboard)

@dp.message(lambda message: message.text == "🔍 Найти олимпиады")
async def start_search(message: types.Message):
    chat_id = message.chat.id
    user_filters[chat_id] = {}
    user_state[chat_id] = "subject"
    subjects = get_all_subjects()
    subjects.sort()
    options = ["⬅️ Вернуться на главную"] + ["Любой"] + subjects 
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True
    )
    await message.answer("Выберите предмет:", reply_markup=keyboard)

@dp.message(lambda message: user_state.get(message.chat.id) == "subject")
async def handle_subject(message: types.Message):
    chat_id = message.chat.id
    chosen = message.text
    user_filters[chat_id]["subject"] = chosen
    user_state[chat_id] = "grade"
    grades = get_all_grades()
    options = ["⬅️ Вернуться на главную"] + ["Любой"] + grades
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True
    )
    await message.answer("Выберите класс:", reply_markup=keyboard)

@dp.message(lambda message: user_state.get(message.chat.id) == "grade")
async def handle_grade(message: types.Message):
    chat_id = message.chat.id
    chosen = message.text
    user_filters[chat_id]["grade"] = chosen
    user_state[chat_id] = "level"
    levels = get_all_levels()
    options = ["⬅️ Вернуться на главную"] + levels  # уже включает "Любой" и "Нет"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True
    )
    await message.answer("Выберите уровень:", reply_markup=keyboard)

@dp.message(lambda message: user_state.get(message.chat.id) == "level")
async def handle_level(message: types.Message):
    chat_id = message.chat.id
    chosen = message.text
    user_filters[chat_id]["level"] = chosen
    user_state[chat_id] = None
    filters = user_filters.get(chat_id, {})
    subject = filters.get("subject")
    grade = filters.get("grade")
    level = filters.get("level")
    # Получаем олимпиады по предмету и уровню
    olympiads = get_olympiads(subject, level)
    # Фильтруем по классу, если выбран не "Любой"
    if grade and grade != "Любой":
        olympiads = filter_by_grade(olympiads, grade)
    if olympiads:
        user_olympiads_state[chat_id] = {"olympiads": olympiads, "index": 0}
        await send_next(chat_id, 0)
    else:
        await message.answer("По заданным фильтрам олимпиад не найдено.")
        await start_command(message)

# --- Обработчики подписки, отписки и листания ---

@dp.message(lambda message: message.text == "📋 Мои подписки")
async def show_subscriptions(message: types.Message):
    user_id = message.chat.id
    user_state[user_id]="subscribe" if user_state[user_id] not in ["subscribe","unsubscribe"] else user_state[user_id]
    subscriptions = get_subscriptions(user_id)
    if subscriptions:
        response = "Введите ID олимпиады для подписки или нажмите на кнопки"+"\nВаши подписки:\n" + "\n".join([f"{s[1]} (ID: {s[0]})" for s in subscriptions]) if user_state[user_id]=="subscribe" else "Введите ID олимпиады для отписки или нажмите на кнопки"+"\nВаши подписки:\n" + "\n".join([f"{s[1]} (ID: {s[0]})" for s in subscriptions])
        buttons = [[KeyboardButton(text="⬅️ Вернуться на главную")]] + [[KeyboardButton(text="Сменить режим на отписку" if user_state[user_id]=="subscribe" else "Сменить режим на подписку")]] +[[KeyboardButton(text=f"❌ Отписаться от {s[1]}")] for s in subscriptions] 
        keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer(response, reply_markup=keyboard)
    else:
        response = "Введите ID олимпиады для подписки"+"\nПодписок нет." if user_state[user_id]=="subscribe" else "Введите ID олимпиады для отписки"+"\nПодписок нет."
        buttons = [[KeyboardButton(text="⬅️ Вернуться на главную")]] + [[KeyboardButton(text="Сменить режим на отписку" if user_state[user_id]=="subscribe" else "Сменить режим на подписку")]] +[[KeyboardButton(text=f"❌ Отписаться от {s[1]}")] for s in subscriptions] 
        keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer(response, reply_markup=keyboard)

@dp.message(lambda message: message.text == "Сменить режим на подписку" or message.text == "Сменить режим на отписку")
async def change_subscribe_mode(message: types.Message):
    chat_id = message.chat.id
    if message.text == "Сменить режим на подписку":
        user_state[chat_id]="subscribe"
        await message.answer("Изменено на режим подписки")
    else: 
        user_state[chat_id]="unsubscribe"
        await message.answer("Изменено на режим отписки")
    await show_subscriptions(message)
    

@dp.message(lambda message: message.text == "➡️ Далее")
async def next_olympiad(message: types.Message):
    chat_id = message.chat.id
    state = user_olympiads_state.get(chat_id)
    if state:
        index = state.get("index", 0) + 1
        await send_next(chat_id, index)
    else:
        await message.answer("Нет активного списка олимпиад.")
        await start_command(message)



@dp.message(lambda message: message.text == "✅ Подписаться")
async def subscribe_current(message: types.Message):
    chat_id = message.chat.id
    state = user_olympiads_state.get(chat_id)
    if state:
        index = state.get("index", 0)
        olympiads = state.get("olympiads", [])
        if index < len(olympiads):
            olympiad = olympiads[index]
            subscribe_user(chat_id, olympiad[0])
        else:
            await message.answer("Нет активной олимпиады для подписки.")
            await start_command(message)
    else:
        await message.answer("Нет активного списка олимпиад.")
        await start_command(message)

@dp.message(lambda message: message.text == "❌ Отписаться")
async def unsubscribe_current(message: types.Message):
    chat_id = message.chat.id
    state = user_olympiads_state.get(chat_id)
    if state:
        index = state.get("index", 0)
        olympiads = state.get("olympiads", [])
        if index < len(olympiads):
            olympiad = olympiads[index]
            unsubscribe_user(chat_id, olympiad[0])
        else:
            await message.answer("Нет активной олимпиады для отписки.")
            await start_command(message)
    else:
        await message.answer("Нет активного списка олимпиад.")
        await start_command(message)

@dp.message(lambda message: user_state.get(message.chat.id) == "subscribe" and not message.text.startswith("❌ Отписаться от "))
async def subscribe_from_list(message: types.Message):
    chat_id = message.chat.id
    try:
        subscribe_user(chat_id, int(message.text))
        await show_subscriptions(message)
    except:
        await message.answer("Олимпиада не найдена.")
        await show_subscriptions(message)
@dp.message(lambda message: message.text.startswith("❌ Отписаться от ") or user_state.get(message.chat.id) == "unsubscribe")
async def unsubscribe_from_list(message: types.Message):
    user_id = message.chat.id
    if message.text.startswith("❌ Отписаться от "):
        olympiad_name = message.text.replace("❌ Отписаться от ", "")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM Olympiads WHERE name = ?", (olympiad_name,))
        result = cursor.fetchone()
        conn.close()
        if result:
            unsubscribe_user(user_id, result[0])
            await show_subscriptions(message)
        else:
            await message.answer("Олимпиада не найдена.")
    else:
        try:
            unsubscribe_user(user_id, int(message.text))
            await show_subscriptions(message)
        except:
            await message.answer("Олимпиада не найдена.")
            await show_subscriptions(message)
async def daily_tasks():
    while True:
        check_notifications()
        await asyncio.sleep(CHECK_INTERVAL)

async def main():
    asyncio.create_task(daily_tasks())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
