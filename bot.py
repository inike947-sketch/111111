import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import anthropic

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config from environment ──────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
CHANNEL_ID      = os.environ.get("CHANNEL_ID", "")          # e.g. @mychannel or -100123456789
ADMIN_IDS       = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
BOT_NAME        = os.environ.get("BOT_NAME", "Мой Telegram Бот")
WELCOME_MSG     = os.environ.get("WELCOME_MSG", "Привет! Я умный бот для канала. Чем могу помочь?")

# ── Anthropic client (optional) ──────────────────────────────────────────────
ai_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# ── In-memory storage ────────────────────────────────────────────────────────
user_sessions: dict[int, list[dict]] = {}
stats = {"messages": 0, "users": set(), "ai_calls": 0}

# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def ai_reply(user_id: int, text: str) -> str:
    """Call Claude with per-user conversation history."""
    if not ai_client:
        return "🤖 AI не настроен. Задайте ANTHROPIC_API_KEY."

    history = user_sessions.setdefault(user_id, [])
    history.append({"role": "user", "content": text})
    if len(history) > 20:
        history = history[-20:]
        user_sessions[user_id] = history

    try:
        resp = ai_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=(
                f"Ты — умный помощник канала «{BOT_NAME}». "
                "Отвечай кратко и по делу. Если вопрос не по теме — вежливо направь пользователя."
            ),
            messages=history,
        )
        answer = resp.content[0].text
        history.append({"role": "assistant", "content": answer})
        stats["ai_calls"] += 1
        return answer
    except Exception as e:
        logger.error("AI error: %s", e)
        return f"⚠️ Ошибка AI: {e}"

# ════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    stats["users"].add(uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Перейти в канал", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")] if CHANNEL_ID else [],
        [InlineKeyboardButton("❓ Помощь", callback_data="help"),
         InlineKeyboardButton("📊 Статистика", callback_data="stats")],
    ])
    await update.message.reply_text(
        f"👋 {WELCOME_MSG}\n\n"
        f"{'🔑 Вы — администратор.' if is_admin(uid) else ''}",
        reply_markup=kb,
    )

async def cmd_help(update: Update, _):
    text = (
        "📖 *Команды:*\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/clear — сбросить историю диалога\n"
        "/stats — статистика (только для админов)\n\n"
        "💬 Просто напишите любой вопрос — отвечу!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_clear(update: Update, _):
    user_sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("🗑️ История диалога очищена.")

async def cmd_stats(update: Update, _):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов.")
        return
    await update.message.reply_text(
        f"📊 *Статистика бота:*\n"
        f"• Сообщений: {stats['messages']}\n"
        f"• Уникальных пользователей: {len(stats['users'])}\n"
        f"• Вызовов AI: {stats['ai_calls']}\n"
        f"• Запущен: {datetime.now():%Y-%m-%d}",
        parse_mode="Markdown",
    )

# Admin broadcast
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов.")
        return
    msg = " ".join(ctx.args)
    if not msg:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return
    if not CHANNEL_ID:
        await update.message.reply_text("⚠️ CHANNEL_ID не задан.")
        return
    try:
        await ctx.bot.send_message(chat_id=CHANNEL_ID, text=msg)
        await update.message.reply_text("✅ Сообщение отправлено в канал!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ════════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, _):
    if not update.message or not update.message.text:
        return
    uid = update.effective_user.id
    text = update.message.text.strip()
    stats["messages"] += 1
    stats["users"].add(uid)

    await update.message.chat.send_action("typing")
    reply = await ai_reply(uid, text)
    await update.message.reply_text(reply)

# ════════════════════════════════════════════════════════════════════════════
# CALLBACK QUERY
# ════════════════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "help":
        await cmd_help(update, ctx)
    elif q.data == "stats":
        await cmd_stats(update, ctx)

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("clear",     cmd_clear))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started → polling…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
