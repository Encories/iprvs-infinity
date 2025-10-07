import logging
from typing import Optional
import telebot


class TelegramBot:
    def __init__(self, bot_token: str, chat_id: str, logger: logging.Logger) -> None:
        self.logger = logger
        self.chat_id = chat_id
        # Use plain text to avoid Markdown parse errors in Telegram
        self.bot = telebot.TeleBot(bot_token, parse_mode=None)

    def _send(self, text: str) -> None:
        try:
            self.bot.send_message(self.chat_id, text)
            # Avoid logging full text to prevent console Unicode issues
            self.logger.info("Telegram sent")
        except Exception as exc:  # network or API errors
            self.logger.exception(f"Telegram send failed: {exc}")

    def send_signal_notification(self, symbol: str, action: str, direction: Optional[str], amount_usdt: Optional[float], note: Optional[str] = None) -> None:
        parts = [
            "🔔 Новый сигнал",
            f"Symbol: {symbol}",
            f"Action: {action.upper()}",
        ]
        if direction:
            parts.append(f"Direction: {direction.upper()}")
        if amount_usdt is not None:
            parts.append(f"Amount USDT: {amount_usdt}")
        if note:
            parts.append(f"Note: {note}")
        self._send("\n".join(parts))

    def send_order_notification(self, data: dict) -> None:
        parts = [
            "✅ Ордер",
            f"Symbol: {data.get('symbol')}",
            f"Side: {data.get('side')}",
            f"Qty: {data.get('qty')}",
            f"OrderType: {data.get('orderType')}",
            f"Price: {data.get('price')}",
            f"Status: {data.get('status')}",
            f"OrderId: {data.get('orderId')}",
        ]
        note = data.get('note')
        if note:
            parts.append(f"Note: {note}")
        self._send("\n".join(parts))

    def send_error_notification(self, text: str, context: Optional[dict] = None) -> None:
        parts = ["❌ Ошибка", text]
        if context:
            parts.append(f"Context: {context}")
        self._send("\n".join(parts))


