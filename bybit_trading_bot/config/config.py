import os
from dotenv import load_dotenv


load_dotenv()


class Config:
    # Flask
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Webhook auth (HMAC secret)
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "change_me")
    WEBHOOK_MAX_SKEW_SECONDS: int = int(os.getenv("WEBHOOK_MAX_SKEW_SECONDS", "300"))
    WEBHOOK_AUTH_DISABLED: bool = os.getenv("WEBHOOK_AUTH_DISABLED", "false").lower() == "true"

    # Bybit (LIVE only)
    BYBIT_API_KEY: str = os.getenv("BYBIT_API_KEY", "")
    BYBIT_API_SECRET: str = os.getenv("BYBIT_API_SECRET", "")
    BYBIT_CATEGORY: str = "spot"  # Spot trading only
    LEVERAGE_DEFAULT: int = int(os.getenv("LEVERAGE_DEFAULT", "5"))

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Trading settings (USDT notionals)
    DEFAULT_ORDER_TYPE: str = os.getenv("DEFAULT_ORDER_TYPE", "market").lower()
    DEFAULT_AMOUNT_USDT: float = float(os.getenv("DEFAULT_AMOUNT_USDT", "50"))
    MAX_ORDER_SIZE_USDT: float = float(os.getenv("MAX_ORDER_SIZE_USDT", "10000"))
    MIN_ORDER_SIZE_USDT: float = float(os.getenv("MIN_ORDER_SIZE_USDT", "5"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "trading_bot.log")

    # Tunnel (Cloudflare) optional
    TUNNEL_ENABLE: bool = os.getenv("TUNNEL_ENABLE", "false").lower() == "true"
    TUNNEL_BIN: str = os.getenv("TUNNEL_BIN", "cloudflared")

    # Test mode (no trading side-effects)
    TEST: bool = os.getenv("TEST", "false").lower() == "true"

    # Public base URL (for VDS without tunnel), e.g. https://your-domain
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "")


