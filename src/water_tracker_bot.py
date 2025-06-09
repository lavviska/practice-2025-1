from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler, ContextTypes
)
from datetime import time as dt_time
from telegram.error import BadRequest

TOKEN = '7812724913:AAHxJBHmNy6D0nD3W_DgIEiaol7BaAdcL8w'

CHOOSING_TIME, TYPING_TIME, CHOOSING_DAYS, EDIT_MENU = range(4)

user_settings = {}
time_buttons = ['09:00', '12:00', '15:00', '18:00', '21:00']
days_of_week = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
day_map = {'Пн': 0, 'Вт': 1, 'Ср': 2, 'Чт': 3, 'Пт': 4, 'Сб': 5, 'Вс': 6}

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.data['user_id']
    try:
        await context.bot.send_message(chat_id=user_id, text="💧 Пей воду! Время напоминания! 💦")
    except Exception as e:
        print(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")

def schedule_reminders(app, user_id):
    if user_id not in user_settings:
        return

    current_jobs = app.job_queue.get_jobs_by_name(str(user_id))
    for job in current_jobs:
        job.schedule_removal()

    times = user_settings[user_id].get('times', [])
    days = user_settings[user_id].get('days', set())

    if not times or not days:
        return

    for t_str in times:
        try:
            hour, minute = map(int, t_str.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                continue
            for day in days:
                weekday_num = day_map.get(day)
                if weekday_num is not None:
                    app.job_queue.run_daily(
                        send_reminder,
                        time=dt_time(hour, minute),
                        days=(weekday_num,),
                        name=str(user_id),
                        data={'user_id': user_id}
                    )
        except (ValueError, AttributeError):
            continue

async def safe_edit_message(query, text=None, reply_markup=None):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise e
        # Игнорируем ошибку, если сообщение не изменилось

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    keyboard = [
        [InlineKeyboardButton("🆕 Новые напоминания", callback_data="new")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="edit")],
        [InlineKeyboardButton("🗑 Удалить все", callback_data="delete")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            "🌊 Привет! Я помогу тебе не забывать пить воду!\n\nВыбери действие:",
            reply_markup=reply_markup
        )
    else:
        await safe_edit_message(
            update.callback_query,
            text="🌊 Привет! Я помогу тебе не забывать пить воду!\n\nВыбери действие:",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

async def delete_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id in user_settings:
        user_settings.pop(user_id)

    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    for job in current_jobs:
        job.schedule_removal()

    await safe_edit_message(query, text="❌ Все напоминания удалены!")
    return ConversationHandler.END

async def edit_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    keyboard = [
        [InlineKeyboardButton("⏰ Изменить время", callback_data="edit_time")],
        [InlineKeyboardButton("📅 Изменить дни", callback_data="edit_days")],
        [InlineKeyboardButton("✅ Назад", callback_data="back")]
    ]
    await safe_edit_message(
        query,
        text="Что хочешь изменить?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_MENU

async def edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "edit_time":
        return await ask_time_options(update, context)
    elif data == "edit_days":
        return await ask_days(update, context)
    elif data == "back":
        return await start(update, context)
    return EDIT_MENU

async def ask_time_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    keyboard = [[InlineKeyboardButton(t, callback_data=f"time_{t}")] for t in time_buttons]
    keyboard.append([InlineKeyboardButton("⌨️ Ввести своё время", callback_data="time_custom")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await safe_edit_message(
        query,
        text="Выбери время:",
        reply_markup=reply_markup
    )
    return CHOOSING_TIME

async def time_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data
    
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    if data == "time_custom":
        await safe_edit_message(query, text="Введи время в формате ЧЧ:ММ:")
        return TYPING_TIME
    else:
        t = data.split('_')[1]
        if t not in user_settings[user_id]['times']:
            user_settings[user_id]['times'].append(t)
        return await show_edit_options(update, context)

async def typing_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    try:
        if len(text) != 5 or text[2] != ':' or not text.replace(':', '').isdigit():
            raise ValueError
        hour, minute = map(int, text.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("Неверный формат. Попробуй ЧЧ:ММ (например 08:30), где 0 <= ЧЧ <= 23 и 0 <= ММ <= 59")
        return TYPING_TIME

    if text not in user_settings[user_id]['times']:
        user_settings[user_id]['times'].append(text)
    
    return await show_edit_options(update, context)

async def ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    buttons = []
    for day in days_of_week:
        mark = "✅" if day in user_settings[user_id]['days'] else "❌"
        buttons.append(InlineKeyboardButton(f"{mark} {day}", callback_data=f"day_{day}"))
    
    buttons.append(InlineKeyboardButton("🗓 Каждый день", callback_data="day_everyday"))
    buttons.append(InlineKeyboardButton("✅ Готово", callback_data="done_days"))
    
    keyboard = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await safe_edit_message(
        query,
        text="Выбери дни:",
        reply_markup=reply_markup
    )
    return CHOOSING_DAYS

async def days_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()
    
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    if data == "done_days":
        if not user_settings[user_id]['days']:
            await query.answer(text="Нужно выбрать хотя бы один день!", show_alert=True)
            return CHOOSING_DAYS
        return await show_edit_options(update, context)

    elif data == "day_everyday":
        if len(user_settings[user_id]['days']) == 7:
            user_settings[user_id]['days'] = set()
        else:
            user_settings[user_id]['days'] = set(days_of_week)
    else:
        day = data.split('_')[1]
        if day in user_settings[user_id]['days']:
            user_settings[user_id]['days'].remove(day)
        else:
            user_settings[user_id]['days'].add(day)

    return await ask_days(update, context)

async def show_edit_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_settings:
        user_settings[user_id] = {'times': [], 'days': set()}

    times = ', '.join(user_settings[user_id]['times']) if user_settings[user_id]['times'] else "не выбрано"
    days = ', '.join(sorted(user_settings[user_id]['days'], key=lambda d: days_of_week.index(d))) if user_settings[user_id]['days'] else "не выбраны"
    
    text = f"🧃 Напоминания настроены!\n\n⏰ Время: *{times}*\n📅 Дни: *{days}*"

    if update.callback_query:
        await safe_edit_message(
            update.callback_query,
            text=text,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

    schedule_reminders(context.application, user_id)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, всё отменено.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_TIME: [
                CallbackQueryHandler(time_chosen, pattern=r"^time_"),
                CallbackQueryHandler(ask_time_options, pattern="^time_custom$")
            ],
            TYPING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, typing_time)],
            CHOOSING_DAYS: [CallbackQueryHandler(days_chosen, pattern=r"^(day_|done_days|day_everyday)$")],
            EDIT_MENU: [CallbackQueryHandler(edit_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(delete_settings, pattern="^delete$"))
    app.add_handler(CallbackQueryHandler(edit_settings, pattern="^edit$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^new$"))

    print("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()