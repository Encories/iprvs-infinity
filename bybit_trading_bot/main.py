import threading
from .modules.webhook_server import create_app
from .modules.bybit_trader import BybitTrader
from .modules.telegram_bot import TelegramBot
from .modules.logger import setup_logger
from .config.config import Config
from .modules.tunnel import CloudflareTunnel


def main() -> None:
    logger = setup_logger(
        level=Config.LOG_LEVEL,
        log_file=Config.LOG_FILE,
    )

    telegram = TelegramBot(
        bot_token=Config.TELEGRAM_BOT_TOKEN,
        chat_id=Config.TELEGRAM_CHAT_ID,
        logger=logger,
    )

    trader = BybitTrader(
        api_key=Config.BYBIT_API_KEY,
        api_secret=Config.BYBIT_API_SECRET,
        default_leverage=Config.LEVERAGE_DEFAULT,
        test_mode=Config.TEST,
        logger=logger,
        notifier=telegram,
    )

    app = create_app(trader=trader, notifier=telegram, logger=logger)

    # Optional: start Cloudflare Tunnel
    if Config.TUNNEL_ENABLE and not Config.PUBLIC_BASE_URL:
        local_url = f"http://{Config.FLASK_HOST}:{Config.FLASK_PORT}"
        def on_url(url: str) -> None:
            logger.info(f"Public webhook URL: {url}/webhook")
            telegram._send(f"Public webhook URL: {url}/webhook")
        tunnel = CloudflareTunnel(
            bin_path=Config.TUNNEL_BIN,
            local_url=local_url,
            logger=logger,
            on_url=on_url,
        )
        tunnel.start()
    elif Config.PUBLIC_BASE_URL:
        logger.info(f"Use this webhook URL: {Config.PUBLIC_BASE_URL.rstrip('/')}/webhook")
        telegram._send(f"Use this webhook URL: {Config.PUBLIC_BASE_URL.rstrip('/')}/webhook")

    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=Config.FLASK_DEBUG)


if __name__ == "__main__":
    main()


