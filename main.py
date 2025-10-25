import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Состояния диалога
ENTRY_PRICE, TAKE_PROFIT, STOP_LOSS, RISK_AMOUNT = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 *Трейдинг калькулятор*\n\n"
        "Используй /calc для расчета позиции\n"
        "/help - помощь",
        parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
*📊 Как использовать:*

1. /calc - начать расчет
2. Вводи параметры по очереди:
   - Цена входа (USDT)
   - Тейк-профит (USDT) 
   - Стоп-лосс (USDT)
   - Сумма риска (USDT)

*Пример:*
50000
52000  
49000
100
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 *Цена входа (USDT):*",
                                    parse_mode='Markdown')
    return ENTRY_PRICE


async def entry_price_input(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['entry_price'] = price
        await update.message.reply_text("🎯 *Тейк-профит (USDT):*",
                                        parse_mode='Markdown')
        return TAKE_PROFIT
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return ENTRY_PRICE


async def take_profit_input(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    try:
        tp = float(update.message.text)
        context.user_data['take_profit'] = tp
        await update.message.reply_text("🛑 *Стоп-лосс (USDT):*",
                                        parse_mode='Markdown')
        return STOP_LOSS
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return TAKE_PROFIT


async def stop_loss_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sl = float(update.message.text)
        context.user_data['stop_loss'] = sl
        await update.message.reply_text("💸 *Сумма риска (USDT):*",
                                        parse_mode='Markdown')
        return RISK_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return STOP_LOSS


async def risk_amount_input(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    try:
        risk = float(update.message.text)
        entry = context.user_data['entry_price']
        tp = context.user_data['take_profit']
        sl = context.user_data['stop_loss']

        # Проверка логики
        if (tp > entry and sl > entry) or (tp < entry and sl < entry):
            await update.message.reply_text(
                "❌ TP и SL должны быть по разные стороны от цены входа!")
            return ConversationHandler.END

        # Расчеты
        price_diff = abs(entry - sl)
        position_size = (risk / price_diff) * entry

        # Плечо (макс 10x)
        leverage = min(10, max(1, int(position_size / risk)))
        margin = position_size / leverage

        # Прибыль
        profit_diff = abs(tp - entry)
        potential_profit = (position_size / entry) * profit_diff
        risk_reward = potential_profit / risk

        # Результат
        result = f"""
📊 *Результаты:*

*💰 Размер позиции:* {position_size:,.0f} USDT
*⚖️ Плечо:* {leverage}x  
*💵 Маржа:* {margin:,.0f} USDT
*📈 Прибыль:* {potential_profit:,.0f} USDT
*🎯 Риск/Прибыль:* 1:{risk_reward:.1f}

*Параметры:*
Вход: {entry:,.0f}
TP: {tp:,.0f}
SL: {sl:,.0f}
"""
        await update.message.reply_text(result, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено")
    return ConversationHandler.END


def main():
    # Токен из переменных окружения
    TOKEN = os.environ['TELEGRAM_BOT_TOKEN']

    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Диалог расчета
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('calc', calc_start)],
        states={
            ENTRY_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               entry_price_input)
            ],
            TAKE_PROFIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               take_profit_input)
            ],
            STOP_LOSS:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, stop_loss_input)],
            RISK_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               risk_amount_input)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)])

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)

    # Запуск
    print("🚀 Бот запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()
