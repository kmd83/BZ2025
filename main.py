from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)

import db, mealplans
from config import BOT_TOKEN, GOALS, ACTIVITY

# ===== UI helpers =====
def build_main_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton("🧮 Розрахувати план"), KeyboardButton("🎯 Мета")],
        [KeyboardButton("📋 Профіль"), KeyboardButton("⚖️ Записати вагу")],
        [KeyboardButton("📈 Історія ваги"), KeyboardButton("ℹ️ Допомога")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

GOAL_PREFIX = "goal:"

# ===== Calculations =====
def bmr(sex:str, age:int, h:float, w:float) -> float:
    sex = (sex or '').lower()
    return 10*w + 6.25*h - 5*age + (5 if sex.startswith('m') else -161)

def tdee(user:dict) -> float:
    return bmr(user['sex'], int(user['age']), float(user['height']), float(user['weight'])) * ACTIVITY.get(int(user['activity']), 1.2)

def target_kcal(tdee_val:float, goal:str) -> float:
    if goal == "loss": return tdee_val * 0.85
    if goal == "gain": return tdee_val * 1.15
    return tdee_val

def macros_from_profile(user: dict, kcal: float):
    weight = float(user['weight'])
    p = 1.8 * weight                 # білок г/день
    f = max(0.8 * weight, 45)        # жири г/день, мінімум 45 г
    carbs = (kcal - (p*4 + f*9)) / 4 # вуглеводи г/день
    return round(p), round(f), round(max(carbs, 0))

# ===== Start screen =====
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await c.bot.set_my_commands([
        BotCommand("start", "стартове вікно"),
        BotCommand("menu", "кнопки дій"),
        BotCommand("profile", "покрокове налаштування профілю"),
        BotCommand("setgoal", "мета: loss/maintain/gain"),
        BotCommand("plan", "ккал/макроси + меню"),
        BotCommand("weight", "записати вагу"),
        BotCommand("stats", "історія ваги"),
        BotCommand("help", "допомога"),
        BotCommand("cancel", "скасувати поточний крок"),
    ])

    caption = (
        "<b>Привіт! 👋</b>\n"
        "Це твій бот-помічник у питаннях здорового способу життя\n"
        "від служби доставки раціонів <b>«Будь Здоров»</b> 🥗✨\n\n"
        "Натисни «📋 Профіль» для покрокового налаштування або скористайся кнопками нижче."
    )

    try:
        with open("assets/logo.jpg", "rb") as f:
            await u.message.reply_photo(photo=f, caption=caption, parse_mode=ParseMode.HTML, reply_markup=build_main_kb())
            return
    except FileNotFoundError:
        pass

    url = "https://via.placeholder.com/1200x675.png?text=Bud%27+Zdorov"
    await u.message.reply_photo(photo=url, caption=caption, parse_mode=ParseMode.HTML, reply_markup=build_main_kb())

async def menu_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("Меню:", reply_markup=build_main_kb())

# ===== Goal inline menu =====
async def goal_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("🥗 Схуднення", callback_data=f"{GOAL_PREFIX}loss"),
        InlineKeyboardButton("⚖️ Підтримка", callback_data=f"{GOAL_PREFIX}maintain"),
        InlineKeyboardButton("💪 Набір", callback_data=f"{GOAL_PREFIX}gain"),
    ]]
    await u.message.reply_text("Обери мету:", reply_markup=InlineKeyboardMarkup(kb))

async def goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if not data.startswith(GOAL_PREFIX):
        return
    goal = data[len(GOAL_PREFIX):]
    if goal not in GOALS:
        await q.edit_message_text("Невірне значення мети.")
        return
    db.set_goal(q.from_user.id, goal)
    await q.edit_message_text(f"Мета збережена: {GOALS[goal]} ✅")

# ===== Profile Wizard (Conversation) =====
GENDER, AGE, HEIGHT, WEIGHT, ACTIVITY, DONE = range(6)

async def profile_entry(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("👨 Чоловік", callback_data="gender:m"),
        InlineKeyboardButton("👩 Жінка",  callback_data="gender:f"),
    ]]
    await u.message.reply_text("Налаштуємо профіль. Обери стать:", reply_markup=InlineKeyboardMarkup(kb))
    return GENDER

async def profile_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["sex"] = q.data.split(":",1)[1]
    await q.edit_message_text("Вкажи свій вік у роках (наприклад, 30):")
    return AGE

async def profile_age(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        age = int((u.message.text or "").strip())
    except Exception:
        await u.message.reply_text("Вік має бути числом. Спробуй ще раз:")
        return AGE
    c.user_data["age"] = age
    await u.message.reply_text("Вкажи зріст у см (наприклад, 175):")
    return HEIGHT

async def profile_height(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        h = float((u.message.text or "").strip())
    except Exception:
        await u.message.reply_text("Зріст має бути числом. Спробуй ще раз:")
        return HEIGHT
    c.user_data["height"] = h
    await u.message.reply_text("Вкажи вагу у кг (наприклад, 70.5):")
    return WEIGHT

async def profile_weight(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        w = float((u.message.text or "").strip())
    except Exception:
        await u.message.reply_text("Вага має бути числом. Спробуй ще раз:")
        return WEIGHT
    c.user_data["weight"] = w
    kb = [
        [InlineKeyboardButton("🛋️ Дуже низька", callback_data="act:1"), InlineKeyboardButton("🚶 Легка", callback_data="act:2")],
        [InlineKeyboardButton("🏃 Середня", callback_data="act:3"), InlineKeyboardButton("🏋️ Висока", callback_data="act:4")],
        [InlineKeyboardButton("🔥 Дуже висока", callback_data="act:5")],
    ]
    await u.message.reply_text("Обери рівень активності:", reply_markup=InlineKeyboardMarkup(kb))
    return ACTIVITY

async def profile_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    activity = int(q.data.split(":",1)[1])
    context.user_data["activity"] = activity
    uid = q.from_user.id
    db.set_profile(uid,
                   context.user_data["sex"],
                   context.user_data["age"],
                   context.user_data["height"],
                   context.user_data["weight"],
                   context.user_data["activity"])
    user = db.get_user(uid)
    await q.edit_message_text(f"✅ Профіль збережено! Вік: {user['age']}, зріст: {user['height']} см, вага: {user['weight']} кг, активність: {user['activity']}")
    return ConversationHandler.END

async def profile_cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("Налаштування профілю скасовано.", reply_markup=build_main_kb())
    return ConversationHandler.END

# ===== Plan / Weight / Stats / Help =====
async def plan(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(u.effective_user.id)
    if not user:
        await u.message.reply_text("Спочатку налаштуй профіль: натисни «📋 Профіль».")
        return
    goal = user.get("goal") or "maintain"
    kcal = target_kcal(tdee(user), goal)
    p,f,carb = macros_from_profile(user, kcal)
    menu = "\\n".join(f"• {x}" for x in mealplans.sample(goal))
    await u.message.reply_text(
        f"Мета: {GOALS.get(goal, goal)}\\n"
        f"Ккал: ~{round(kcal)}\\n"
        f"Макроси: білки {p} г, жири {f} г, вуглеводи {carb} г\\n\\n"
        f"Приблизне меню:\\n{menu}",
        reply_markup=build_main_kb()
    )

# (остальные команды weight, stats, help — такие же как раньше)

# ===== App bootstrap =====
if __name__ == "__main__":
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("plan", plan))
    # Conversation для профілю
    conv = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_entry)],
        states={
            GENDER:   [CallbackQueryHandler(profile_gender, pattern="^gender:(m|f)$")],
            AGE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_age)],
            HEIGHT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_height)],
            WEIGHT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_weight)],
            ACTIVITY: [CallbackQueryHandler(profile_activity, pattern="^act:[1-5]$")],
        },
        fallbacks=[CommandHandler("cancel", profile_cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(goal_callback, pattern=f"^{GOAL_PREFIX}"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_cmd))
    print("Bot running")
    app.run_polling()
