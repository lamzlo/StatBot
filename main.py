import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
ENTRY_PRICE, TAKE_PROFIT, STOP_LOSS, RISK_AMOUNT = range(4)

def parse_number(text: str) -> float:
    """Парсер чисел"""
    try:
        cleaned = text.replace(',', '.').replace(' ', '')
        return float(cleaned)
    except ValueError:
        raise ValueError("Некорректное число")

def format_currency(value: float) -> str:
    """Форматирование валюты без разделителей"""
    if value.is_integer():
        return str(int(value))
    else:
        formatted = f"{value:.4f}"
        return formatted.rstrip('0').rstrip('.')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    
    keyboard = [['📊 Рассчитать позицию']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🎯 *Трейдинг Калькулятор*\n\n"
        "Быстрый расчет позиции с риск-менеджментом\n\n"
        "Нажми *📊 Рассчитать позицию* чтобы начать",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💰 *Цена входа (USDT):*",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    return ENTRY_PRICE

async def entry_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = parse_number(update.message.text)
        if price <= 0:
            await update.message.reply_text("❌ Цена должна быть > 0\n💰 Введите цену входа:")
            return ENTRY_PRICE
        context.user_data['entry_price'] = price
        await update.message.reply_text("🎯 *Тейк-профит (USDT):*", parse_mode='Markdown')
        return TAKE_PROFIT
    except ValueError:
        await update.message.reply_text("❌ Введите число\n💰 Цена входа:")
        return ENTRY_PRICE

async def take_profit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tp = parse_number(update.message.text)
        if tp <= 0:
            await update.message.reply_text("❌ Цена должна быть > 0\n🎯 Тейк-профит:")
            return TAKE_PROFIT
        context.user_data['take_profit'] = tp
        await update.message.reply_text("🛑 *Стоп-лосс (USDT):*", parse_mode='Markdown')
        return STOP_LOSS
    except ValueError:
        await update.message.reply_text("❌ Введите число\n🎯 Тейк-профит:")
        return TAKE_PROFIT

async def stop_loss_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sl = parse_number(update.message.text)
        if sl <= 0:
            await update.message.reply_text("❌ Цена должна быть > 0\n🛑 Стоп-лосс:")
            return STOP_LOSS
        context.user_data['stop_loss'] = sl
        await update.message.reply_text("💸 *Сумма риска (USDT):*", parse_mode='Markdown')
        return RISK_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Введите число\n🛑 Стоп-лосс:")
        return STOP_LOSS

async def risk_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        risk = parse_number(update.message.text)
        if risk <= 0:
            await update.message.reply_text("❌ Риск должен быть > 0\n💸 Сумма риска:")
            return RISK_AMOUNT
            
        entry = context.user_data['entry_price']
        tp = context.user_data['take_profit']
        sl = context.user_data['stop_loss']
        
        # Проверка логики
        if (tp > entry and sl > entry) or (tp < entry and sl < entry):
            error_msg = "❌ *Ошибка логики!*\n\n"
            if tp > entry:
                error_msg += "Для *ЛОНГА*:\n• TP > Входа ✅\n• SL < Входа ❌"
            else:
                error_msg += "Для *ШОРТА*:\n• TP < Входа ✅\n• SL > Входа ❌"
            
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return await show_restart_button(update)
        
        # Расчеты
        price_diff = abs(entry - sl)
        position_size = (risk / price_diff) * entry
        leverage = min(10, max(1, int(position_size / risk)))
        margin = position_size / leverage
        profit_diff = abs(tp - entry)
        potential_profit = (position_size / entry) * profit_diff
        risk_reward = potential_profit / risk
        
        # Тип сделки
        trade_type = "🟢 ЛОНГ" if tp > entry else "🔴 ШОРТ"
        color = "🟢" if tp > entry else "🔴"
        
        # Оценка
        if risk_reward >= 3: rating = "⭐️⭐️⭐️ ОТЛИЧНО"
        elif risk_reward >= 2: rating = "⭐️⭐️ ХОРОШО"
        elif risk_reward >= 1: rating = "⭐️ НОРМАЛЬНО"
        else: rating = "⚠️ РИСКОВАННО"
        
        # Результат
        result = f"""
{color} *РЕЗУЛЬТАТ РАСЧЕТА* {color}
*{trade_type}* | {rating}

📊 *Параметры позиции:*
├ Размер: {format_currency(position_size)} USDT
├ Плечо: {leverage}x
├ Маржа: {format_currency(margin)} USDT
├ Прибыль: {format_currency(potential_profit)} USDT
└ R/R: 1:{risk_reward:.2f}

🎯 *Уровни:*
├ Вход: {format_currency(entry)}
├ TP: {format_currency(tp)}
├ SL: {format_currency(sl)}
└ Риск: {format_currency(risk)} USDT
"""
        await update.message.reply_text(result, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка расчета")
    
    return await show_restart_button(update)

async def show_restart_button(update: Update):
    keyboard = [['📊 Рассчитать позицию']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "✨ *Расчет завершен!*\n\nНажми *📊 Рассчитать позицию* для следующей позиции",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '📊 Рассчитать позицию':
        return await calc_start(update, context)
    
    keyboard = [['📊 Рассчитать позицию']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Нажми *📊 Рассчитать позицию* чтобы начать расчет",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

def main():
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    # Диалог расчета
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ],
        states={
            ENTRY_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, entry_price_input)],
            TAKE_PROFIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, take_profit_input)],
            STOP_LOSS: [MessageHandler(filters.TEXT & ~filters.COMMAND, stop_loss_input)],
            RISK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, risk_amount_input)],
        },
        fallbacks=[],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    logger.info("🚀 Бот запущен на Render!")
    application.run_polling()

if __name__ == '__main__':
    main()
