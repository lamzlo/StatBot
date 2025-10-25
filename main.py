import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния диалога
ENTRY_PRICE, TAKE_PROFIT, STOP_LOSS, RISK_AMOUNT = range(4)


def parse_number(text: str) -> float:
    """Умный парсер чисел с точкой и запятой"""
    try:
        # Заменяем запятые на точки и убираем пробелы
        cleaned = text.replace(',', '.').replace(' ', '')
        return float(cleaned)
    except ValueError:
        raise ValueError("Не могу преобразовать в число")


def format_currency(value: float) -> str:
    """Форматирование валюты без запятых и пробелов"""
    if value.is_integer():
        return f"{int(value)}"
    else:
        # Оставляем только 2 знака после запятой без лишних нулей
        formatted = f"{value:.2f}"
        # Убираем .00 в конце если есть
        if formatted.endswith('.00'):
            return formatted[:-3]
        return formatted


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 *Трейдинг калькулятор*\n\n"
        "Используй /calc для расчета позиции\n"
        "/help - помощь\n\n"
        "💡 *Можно использовать и точку и запятую:*\n"
        "50000.50 или 50000,50",
        parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
*📊 Как использовать:*

1. /calc - начать расчет
2. Вводи параметры по очереди:

*Формат чисел:*
- Можно использовать точку: `50000.50`
- Можно использовать запятую: `50000,50`
- Пробелы игнорируются: `50 000.50`

*Пример расчета:*
Цена входа: 50000
Тейк-профит: 52000
Стоп-лосс: 49000
Сумма риска: 100
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 *Цена входа (USDT):*\n\n"
        "💡 Можно использовать точку или запятую:\n"
        "50000.50 или 50000,50",
        parse_mode='Markdown')
    return ENTRY_PRICE


async def entry_price_input(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    try:
        price = parse_number(update.message.text)
        if price <= 0:
            await update.message.reply_text(
                "❌ Цена должна быть больше 0. Попробуй снова:")
            return ENTRY_PRICE

        context.user_data['entry_price'] = price
        await update.message.reply_text("🎯 *Тейк-профит (USDT):*",
                                        parse_mode='Markdown')
        return TAKE_PROFIT
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}. Попробуй снова:")
        return ENTRY_PRICE


async def take_profit_input(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    try:
        tp = parse_number(update.message.text)
        if tp <= 0:
            await update.message.reply_text(
                "❌ Цена должна быть больше 0. Попробуй снова:")
            return TAKE_PROFIT

        context.user_data['take_profit'] = tp
        await update.message.reply_text("🛑 *Стоп-лосс (USDT):*",
                                        parse_mode='Markdown')
        return STOP_LOSS
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}. Попробуй снова:")
        return TAKE_PROFIT


async def stop_loss_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sl = parse_number(update.message.text)
        if sl <= 0:
            await update.message.reply_text(
                "❌ Цена должна быть больше 0. Попробуй снова:")
            return STOP_LOSS

        context.user_data['stop_loss'] = sl
        await update.message.reply_text("💸 *Сумма риска (USDT):*",
                                        parse_mode='Markdown')
        return RISK_AMOUNT
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}. Попробуй снова:")
        return STOP_LOSS


async def risk_amount_input(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    try:
        risk = parse_number(update.message.text)
        if risk <= 0:
            await update.message.reply_text(
                "❌ Сумма риска должна быть больше 0. Попробуй снова:")
            return RISK_AMOUNT

        entry = context.user_data['entry_price']
        tp = context.user_data['take_profit']
        sl = context.user_data['stop_loss']

        # Проверка логики цен
        if (tp > entry and sl > entry) or (tp < entry and sl < entry):
            await update.message.reply_text(
                "❌ *Ошибка логики!*\n\n"
                "Тейк-профит и стоп-лосс должны быть по разные стороны от цены входа!\n\n"
                "Для *лонга* (покупки):\n"
                "• Тейк-профит > Цена входа\n"
                "• Стоп-лосс < Цена входа\n\n"
                "Для *шорта* (продажи):\n"
                "• Тейк-профит < Цена входа\n"
                "• Стоп-лосс > Цена входа",
                parse_mode='Markdown')
            # Предлагаем новый расчет
            await update.message.reply_text(
                "🔄 Хочешь попробовать снова? Нажми /calc",
                parse_mode='Markdown')
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

        # Определяем тип сделки
        trade_type = "🟢 ЛОНГ" if tp > entry else "🔴 ШОРТ"

        # Результат
        result = f"""
📊 *Результаты расчета:*
{trade_type}

*💰 Размер позиции:* `{format_currency(position_size)} USDT`
*⚖️ Оптимальное плечо:* `{leverage}x`
*💵 Требуемая маржа:* `{format_currency(margin)} USDT`
*📈 Потенциальная прибыль:* `{format_currency(potential_profit)} USDT`
*🎯 Соотношение Риск/Прибыль:* `1:{risk_reward:.2f}`

*Параметры сделки:*
• Вход: `{format_currency(entry)} USDT`
• Тейк-профит: `{format_currency(tp)} USDT`
• Стоп-лосс: `{format_currency(sl)} USDT`
• Риск: `{format_currency(risk)} USDT`
"""
        await update.message.reply_text(result, parse_mode='Markdown')

        # Дополнительная оценка
        if risk_reward >= 3:
            await update.message.reply_text(
                "✅ *Отличное соотношение!* Хорошая сделка!",
                parse_mode='Markdown')
        elif risk_reward >= 2:
            await update.message.reply_text("⚠️ *Нормальное соотношение*",
                                            parse_mode='Markdown')
        elif risk_reward >= 1:
            await update.message.reply_text(
                "🔶 *Среднее соотношение* - подумай еще", parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "❌ *Плохое соотношение* - риск превышает потенциальную прибыль",
                parse_mode='Markdown')

        # Предлагаем новый расчет
        await update.message.reply_text(
            "🔄 *Хочешь рассчитать еще одну позицию?*\n\n"
            "Нажми /calc для нового расчета\n"
            "/help - если нужна помощь",
            parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка в расчетах: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка в расчетах.\n\n"
            "🔄 Попробуй снова: /calc",
            parse_mode='Markdown')

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Расчет отменен\n\n"
        "🔄 Если хочешь начать заново - нажми /calc",
        parse_mode='Markdown')
    return ConversationHandler.END


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤔 Не понимаю команду\n\n"
        "Используй:\n"
        "/start - начать работу\n"
        "/calc - рассчитать позицию\n"
        "/help - помощь\n\n"
        "💡 Или просто нажми /calc чтобы начать расчет!",
        parse_mode='Markdown')


def main():
    # Токен из переменных окружения
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не установлен!")
        print("📝 Добавьте токен в Secrets (иконка замка слева)")
        return

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
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))

    # Запуск
    print("🚀 Бот запущен!")
    print("💡 Теперь числа выводятся без запятых и пробелов")
    print("💡 После расчета предлагается новый расчет")
    application.run_polling()


if __name__ == '__main__':
    main()
