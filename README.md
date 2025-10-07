## Bybit Futures Trading Bot (TradingView Webhook + Telegram)

Python bot that receives TradingView alerts via webhook, trades Bybit linear (USDT) futures in live mode, and sends Telegram notifications.

### Features
- Flask webhook endpoint `/webhook` with HMAC authentication
- Bybit unified trading (linear USDT perpetuals), live only
- Market/limit orders, dynamic instrument filters (tick/lot size)
- Notional inputs in USDT converted to base-asset quantity
- Exponential backoff for API calls
- Telegram notifications for signals, orders, and errors
- Rotating file and console logging
- TEST mode: dry-run without placing real orders

### Quick start
1. Create and fill `.env` from `.env.example`.
2. Install deps:
```bash
pip install -r requirements.txt
```
3. Run:
```bash
python -m bybit_trading_bot.main
```

### TEST mode (no live orders)
- Enable in `.env`:
```
TEST=true
```
- Behavior: all validations, logging, Telegram, Cloudflare tunnel and price/instrument queries work, but order placement, leverage changes and position closing are simulated only (status `SIMULATED`).

### Optional: Public URL via Cloudflare Tunnel (free)
1) Install cloudflared:
   - Windows: download exe from `https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/` and put it in PATH.
2) Enable in `.env`:
```
TUNNEL_ENABLE=true
TUNNEL_BIN=cloudflared
```
3) Launch the bot as usual. The bot will start `cloudflared tunnel --url http://FLASK_HOST:FLASK_PORT` and print a `https://...trycloudflare.com` URL. Also sent to Telegram.
4) Use `https://...trycloudflare.com/webhook` as the TradingView webhook URL.

### TradingView payload (recommended)
Send a POST JSON to `/webhook` with header `X-Webhook-Signature: hex(hmac_sha256(WEBHOOK_SECRET, raw_body))` and optional `X-Webhook-Timestamp` (unix ms). If headers cannot be set, you may include a body field `key` equal to `WEBHOOK_SECRET` as a fallback.

```json
{
  "ts": 1696500000000,
  "action": "open",          // "open" | "close"
  "direction": "long",        // optional; defaults to "long" if omitted
  "symbol": "BTCUSDT",
  "amount_usdt": 50.0,         // optional; defaults to DEFAULT_AMOUNT_USDT if omitted
  "order_type": "market",     // "market" | "limit"
  "limit_price": 65000.0,      // required if order_type=="limit"
  "leverage": 5,               // optional (used for futures; ignored if not provided)
  "id": "my-strategy-001",    // optional
  "note": "text"               // optional; included in notifications/logs
}
```

Notes:
- `ts` is a unix timestamp in milliseconds to protect against replay; allow small clock skew.
- `direction` defaults to "long" if omitted.
- `amount_usdt` is enforced from `.env` (`DEFAULT_AMOUNT_USDT`) to guarantee a fixed USDT spend per trade; the bot converts to base quantity via best bid/ask and rounds to lot size.
- `close` closes the entire open position for `symbol` by placing a market reduce-only order.

### Security
- Use a strong `WEBHOOK_SECRET` and HMAC header. Enable timestamp header and allow small clock skew only.
- Live trading only. Test thoroughly before enabling strategies.


