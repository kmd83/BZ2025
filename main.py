from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, ConversationHandler, filters
import config

# ===== UI helpers =====
def build_main_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton("🧮 Подобрать необходимый рацион")],
        [KeyboardButton("📋 Оставить заявку")],
        [KeyboardButton("📞 Связаться с менеджером")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

CITY, NAME, PHONE, CALORIES = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.set_my_commands([
        BotCommand("start", "Запуск бота"),
        BotCommand("menu", "Главное меню")
    ])

    caption = (
        "<b>Привет! 👋</b>
"
        "Это бот-помощник по питанию от сервиса доставки рационов <b>«Будь Здоров»</b> 🥗✨

"
        "Нажми кнопку ниже, чтобы продолжить."
    )

    await update.message.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=build_main_kb())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню:", reply_markup=build_main_kb())

# ===== Подбор калоража =====
def mifflin_st_jeor(sex: str, age: int, h: float, w: float) -> float:
    if sex.lower().startswith("m"):
        return 10*w + 6.25*h - 5*age + 5
    else:
        return 10*w + 6.25*h - 5*age - 161

CALORIE_OPTIONS = [900, 1200, 1500, 2000, 2500, 3000]

async def pick_calories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите данные в формате: пол(m/f), возраст, рост(см), вес(кг).
"
        "Пример: m 30 175 70"
    )

async def handle_calories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sex, age, h, w = update.message.text.split()
        kcal = mifflin_st_jeor(sex, int(age), float(h), float(w))
        closest = min(CALORIE_OPTIONS, key=lambda x: abs(x-kcal))
        await update.message.reply_text(f"Ваш расчетный калораж: ~{round(kcal)} ккал.
"
                                        f"Рекомендуем ближайший рацион: {closest} ккал.")
    except:
        await update.message.reply_text("Ошибка ввода. Попробуйте еще раз.")

# ===== Заявка =====
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Киев", callback_data="city:kyiv"),
           InlineKeyboardButton("Одесса", callback_data="city:odessa")]]
    await update.message.reply_text("Выберите город:", reply_markup=InlineKeyboardMarkup(kb))
    return CITY

async def order_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["city"] = q.data.split(":")[1]
    await q.edit_message_text("Введите ваше имя:")
    return NAME

async def order_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Введите номер телефона:")
    return PHONE

async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text.strip()
    kb = [[InlineKeyboardButton(f"{c} ккал", callback_data=f"cal:{c}")] for c in CALORIE_OPTIONS]
    await update.message.reply_text("Выберите рацион:", reply_markup=InlineKeyboardMarkup(kb))
    return CALORIES

async def order_calories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cal = q.data.split(":")[1]
    context.user_data["calories"] = cal
    text = (f"📋 Заявка сохранена:
"
            f"Город: {context.user_data['city']}
"
            f"Имя: {context.user_data['name']}
"
            f"Телефон: {context.user_data['phone']}
"
            f"Рацион: {cal} ккал

"
            f"Наш менеджер скоро свяжется с вами ✅")
    await q.edit_message_text(text)
    return ConversationHandler.END

async def order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Заявка отменена.", reply_markup=build_main_kb())
    return ConversationHandler.END

# ===== Контакты =====
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Viber", url="viber://chat?number=%2B380660661411"),
           InlineKeyboardButton("Telegram", url="https://t.me/+380660661411")]]
    await update.message.reply_text("Связаться с менеджером:", reply_markup=InlineKeyboardMarkup(kb))

# ===== Запуск =====
if __name__ == "__main__":
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))

    app.add_handler(MessageHandler(filters.Regex("🧮 Подобрать необходимый рацион"), pick_calories))
    app.add_handler(MessageHandler(filters.Regex("📋 Оставить заявку"), order))
    app.add_handler(MessageHandler(filters.Regex("📞 Связаться с менеджером"), contact))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_calories))

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📋 Оставить заявку"), order)],
        states={
            CITY:      [MessageHandler(filters.ALL, order_city)],
            NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, order_name)],
            PHONE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone)],
            CALORIES:  [MessageHandler(filters.ALL, order_calories)]
        },
        fallbacks=[CommandHandler("cancel", order_cancel)],
    )
    app.add_handler(conv)

    print("Bot running...")
    app.run_polling()
