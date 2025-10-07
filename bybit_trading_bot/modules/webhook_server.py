import hmac
import json
import logging
import time
from hashlib import sha256
from typing import Any, Dict, Optional, Tuple

from flask import Flask, Request, jsonify, request

from ..config.config import Config
from .logger import log_error, log_signal, log_order


def verify_hmac(raw_body: bytes, provided_sig_hex: str, secret: str) -> bool:
    mac = hmac.new(secret.encode(), raw_body, sha256).hexdigest()
    try:
        return hmac.compare_digest(mac, provided_sig_hex)
    except Exception:
        return False


def validate_timestamp(ts_ms: Optional[int], max_skew_seconds: int) -> bool:
    if ts_ms is None:
        return True
    now_ms = int(time.time() * 1000)
    return abs(now_ms - ts_ms) <= max_skew_seconds * 1000


def parse_and_validate_payload(data: Dict[str, Any]) -> Tuple[Optional[dict], Optional[str]]:
    # Recommended payload contract
    # {
    #   "ts": 1696500000000,             # optional unix ms
    #   "action": "open" | "close",
    #   "direction": "long" | "short",  # required if action==open
    #   "symbol": "BTCUSDT",
    #   "amount_usdt": 50.0,              # required if action==open
    #   "order_type": "market"|"limit",
    #   "limit_price": 65000.0,           # required if limit
    #   "leverage": 5                     # optional
    # }

    required_common = ["action", "symbol"]
    for k in required_common:
        if k not in data:
            return None, f"Missing field: {k}"

    action = str(data["action"]).lower()
    symbol = str(data["symbol"]).upper()
    order_type = str(data.get("order_type", Config.DEFAULT_ORDER_TYPE)).lower()
    ts = data.get("ts")
    leverage = data.get("leverage")

    if action not in ("open", "close"):
        return None, "action must be 'open' or 'close'"
    if order_type not in ("market", "limit"):
        return None, "order_type must be 'market' or 'limit'"

    payload: Dict[str, Any] = {
        "ts": ts,
        "action": action,
        "symbol": symbol,
        "order_type": order_type,
        "leverage": leverage,
    }

    # Optional note passthrough
    if "note" in data and data["note"] is not None:
        payload["note"] = str(data["note"])

    if action == "open":
        direction = str(data.get("direction", "long")).lower()
        # Always use .env amount to enforce fixed USDT notional
        amount_usdt = Config.DEFAULT_AMOUNT_USDT
        if direction not in ("long", "short"):
            return None, "direction must be 'long' or 'short' when action=='open'"
        try:
            amount_usdt_val = float(amount_usdt)
        except Exception:
            return None, "amount_usdt must be a number when action=='open'"
        if amount_usdt_val <= 0:
            return None, "amount_usdt must be > 0 when action=='open'"
        payload["direction"] = direction
        payload["amount_usdt"] = amount_usdt_val
        if order_type == "limit":
            if "limit_price" not in data:
                return None, "limit_price is required for limit orders"
            payload["limit_price"] = float(data["limit_price"])

    return payload, None


def create_app(trader, notifier, logger: logging.Logger) -> Flask:
    app = Flask(__name__)

    @app.route("/webhook", methods=["POST"])
    def webhook_handler():
        try:
            raw = request.get_data() or b""
            sig = request.headers.get("X-Webhook-Signature", "")
            ts_header = request.headers.get("X-Webhook-Timestamp")
            ts_ms = int(ts_header) if ts_header else None

            # Authn: Prefer HMAC header; if absent, allow body key fallback
            if Config.WEBHOOK_AUTH_DISABLED:
                # Auth disabled for local testing only
                try:
                    data = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    log_error(logger, "Invalid JSON (auth disabled)")
                    notifier.send_error_notification("Invalid JSON (auth disabled)")
                    return jsonify({"error": "bad_json"}), 400
            elif sig:
                if not verify_hmac(raw, sig, Config.WEBHOOK_SECRET):
                    log_error(logger, "Invalid HMAC", {"sig": sig})
                    notifier.send_error_notification("Invalid webhook signature")
                    return jsonify({"error": "unauthorized"}), 401

                if not validate_timestamp(ts_ms, Config.WEBHOOK_MAX_SKEW_SECONDS):
                    log_error(logger, "Timestamp skew too large", {"ts": ts_ms})
                    notifier.send_error_notification("Timestamp skew too large")
                    return jsonify({"error": "skew"}), 401

                try:
                    data = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    log_error(logger, "Invalid JSON")
                    notifier.send_error_notification("Invalid JSON")
                    return jsonify({"error": "bad_json"}), 400
            else:
                # Fallback: no header signature; expect { "key": WEBHOOK_SECRET, ... }
                try:
                    data = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    log_error(logger, "Invalid JSON (fallback)")
                    notifier.send_error_notification("Invalid JSON (fallback)")
                    return jsonify({"error": "bad_json"}), 400

                if str(data.get("key", "")) != Config.WEBHOOK_SECRET:
                    log_error(logger, "Invalid fallback key")
                    notifier.send_error_notification("Invalid fallback key")
                    return jsonify({"error": "unauthorized"}), 401

            payload, err = parse_and_validate_payload(data)
            if err:
                log_error(logger, f"Validation error: {err}", data)
                notifier.send_error_notification(f"Validation error: {err}")
                return jsonify({"error": err}), 400

            log_signal(logger, payload)
            notifier.send_signal_notification(
                symbol=payload["symbol"],
                action=payload["action"],
                direction=payload.get("direction"),
                amount_usdt=payload.get("amount_usdt"),
                note=payload.get("note"),
            )

            if payload["action"] == "open":
                symbol = payload["symbol"]
                direction = payload["direction"]
                side = "buy" if direction == "long" else "sell"
                amount_usdt = payload["amount_usdt"]
                order_type = payload["order_type"]
                limit_price = payload.get("limit_price")
                leverage = payload.get("leverage")

                # bounds check
                if amount_usdt < Config.MIN_ORDER_SIZE_USDT or amount_usdt > Config.MAX_ORDER_SIZE_USDT:
                    msg = f"amount_usdt out of bounds [{Config.MIN_ORDER_SIZE_USDT}, {Config.MAX_ORDER_SIZE_USDT}]"
                    log_error(logger, msg, payload)
                    notifier.send_error_notification(msg)
                    return jsonify({"error": msg}), 400

                # ensure leverage set
                trader.ensure_leverage(symbol, leverage)
                try:
                    qty = trader.notional_to_qty(symbol, amount_usdt, side)
                except ValueError as ve:
                    msg = str(ve)
                    log_error(logger, msg, payload)
                    notifier.send_error_notification(msg)
                    return jsonify({"error": msg}), 400
                except Exception as exc:
                    # Likely invalid symbol
                    msg = f"symbol not found or unsupported: {symbol}"
                    log_error(logger, msg, {"symbol": symbol, "exc": str(exc)})
                    notifier.send_error_notification(msg)
                    return jsonify({"error": msg}), 400

                res = trader.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    qty=qty,
                    price=limit_price,
                    reduce_only=False,
                    time_in_force="IOC" if order_type == "market" else "GTC",
                )
                log_order(logger, res)
                notifier.send_order_notification({
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "orderType": order_type,
                    "price": limit_price,
                    "status": res.get("retMsg") or res.get("status"),
                    "orderId": res.get("result", {}).get("orderId"),
                })
                return jsonify({"status": "ok", "result": res}), 200

            else:  # close
                symbol = payload["symbol"]
                res = trader.close_position_market(symbol)
                log_order(logger, res)
                notifier.send_order_notification({
                    "symbol": symbol,
                    "side": "close",
                    "qty": None,
                    "orderType": "market",
                    "price": None,
                    "status": res.get("status"),
                    "orderId": None,
                })
                return jsonify({"status": "ok", "result": res}), 200

        except Exception as exc:
            log_error(logger, f"Unhandled error: {exc}")
            notifier.send_error_notification(f"Unhandled error: {exc}")
            return jsonify({"error": "internal_error"}), 500

    return app


