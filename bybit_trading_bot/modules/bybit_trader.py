import logging
import math
import time
from typing import Any, Dict, Optional, Tuple

from pybit.unified_trading import HTTP


class BybitTrader:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        default_leverage: int,
        test_mode: bool,
        logger: logging.Logger,
        notifier: Any,
    ) -> None:
        self.logger = logger
        self.notifier = notifier
        self.test_mode = test_mode
        # Live endpoint for unified trading
        self.client = HTTP(api_key=api_key, api_secret=api_secret)
        self.default_leverage = default_leverage

    # --- Retry wrapper
    def _with_retry(self, fn, *args, **kwargs):
        delay = 0.5
        for attempt in range(4):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if attempt == 3:
                    self.logger.exception("Bybit API error, no more retries")
                    raise
                safe_msg = str(exc).replace("\u2192", "->").replace("→", "->")
                self.logger.warning(f"Bybit API error: {safe_msg}. Retry in {delay}s")
                time.sleep(delay)
                delay *= 2

    # --- Exchange info helpers
    def get_instrument_info(self, symbol: str) -> Dict[str, Any]:
        res = self._with_retry(self.client.get_instruments_info, category="spot", symbol=symbol)
        info_list = res.get("result", {}).get("list", [])
        if not info_list:
            raise ValueError(f"Symbol not found or not spot: {symbol}")
        return info_list[0]

    def get_spot_filters(self, symbol: str) -> Tuple[float, float, float, float]:
        info = self.get_instrument_info(symbol)
        price_filter = info.get("priceFilter", {})
        lot_size_filter = info.get("lotSizeFilter", {})
        tick = float(price_filter.get("tickSize", "0.1"))
        lot = float(lot_size_filter.get("qtyStep", "0.001"))
        min_qty = float(lot_size_filter.get("minOrderQty", lot))
        min_amt = float(lot_size_filter.get("minOrderAmt", 0) or 0)
        return tick, lot, min_qty, min_amt

    def get_best_price(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        try:
            res = self._with_retry(self.client.get_orderbook, category="spot", symbol=symbol, limit=1)
            a = res.get("result", {}).get("a", [])
            b = res.get("result", {}).get("b", [])
            ask = float(a[0][0]) if a else None
            bid = float(b[0][0]) if b else None
            if bid is not None or ask is not None:
                return bid, ask
        except Exception:
            pass
        res_tk = self._with_retry(self.client.get_tickers, category="spot", symbol=symbol)
        list_ = res_tk.get("result", {}).get("list", [])
        if not list_:
            return None, None
        item = list_[0]
        bid = float(item.get("bid1Price")) if item.get("bid1Price") else None
        ask = float(item.get("ask1Price")) if item.get("ask1Price") else None
        if bid is None and ask is None and item.get("lastPrice"):
            lp = float(item.get("lastPrice"))
            return lp, lp
        return bid, ask

    def ensure_leverage(self, symbol: str, leverage: Optional[int]) -> None:
        return

    def get_position_qty(self, symbol: str) -> float:
        return 0.0

    @staticmethod
    def _round_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step) * step

    def compute_buy_qty(self, symbol: str, amount_usdt: float) -> Tuple[float, Optional[str]]:
        bid, ask = self.get_best_price(symbol)
        price = ask or bid
        if not price:
            raise ValueError("Failed to fetch price for qty calc")
        _, lot, min_qty, min_amt = self.get_spot_filters(symbol)
        qty = self._round_step(amount_usdt / price, lot)
        note = None
        if min_amt > 0 and qty * price < min_amt:
            target_qty = math.ceil((min_amt / price) / lot) * lot
            note = f"Adjusted to meet min notional: ~{min_amt:.2f} USDT"
            qty = target_qty
        if qty < min_qty:
            qty = math.ceil(min_qty / lot) * lot
            note = (note + "; " if note else "") + f"Raised to min qty {min_qty}"
        return qty, note

    def notional_to_qty(self, symbol: str, amount_usdt: float, side: str) -> float:
        if side.lower() == "buy":
            qty, _ = self.compute_buy_qty(symbol, amount_usdt)
            return qty
        bid, ask = self.get_best_price(symbol)
        price = bid or ask
        if not price:
            raise ValueError("Failed to fetch price for qty calc")
        _, lot, min_qty, _ = self.get_spot_filters(symbol)
        qty = self._round_step(amount_usdt / price, lot)
        if qty < min_qty:
            required_usdt = min_qty * price
            raise ValueError(f"amount_usdt too small; need at least ~{required_usdt:.2f} USDT for min qty {min_qty}")
        return qty

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
        time_in_force: str = "IOC",
    ) -> Dict[str, Any]:
        if self.test_mode:
            params: Dict[str, Any] = {
                "category": "spot",
                "symbol": symbol,
                "side": side.capitalize(),
                "orderType": order_type.capitalize(),
                "timeInForce": time_in_force,
                "qty": str(qty),
            }
            self.logger.info(f"TEST MODE: simulate place_order {params}")
            return {"status": "SIMULATED", "result": {"orderId": None}, "request": params}
        params: Dict[str, Any] = {
            "category": "spot",
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": order_type.capitalize(),
            "timeInForce": time_in_force,
            "qty": str(qty),
        }
        res = self._with_retry(self.client.place_order, **params)
        return res

    def close_position_market(self, symbol: str) -> Dict[str, Any]:
        if self.test_mode:
            self.logger.info(f"TEST MODE: simulate close_position for {symbol}")
            return {"status": "SIMULATED_CLOSE"}
        # Spot: sell entire available base asset balance
        base_ccy = symbol.replace("USDT", "")
        res_bal = self._with_retry(self.client.get_wallet_balance, accountType="UNIFIED")
        list_ = res_bal.get("result", {}).get("list", [])
        total_qty = 0.0
        for acct in list_:
            for c in acct.get("coin", []):
                if c.get("coin") == base_ccy:
                    total_qty += float(c.get("free", "0"))
        if total_qty <= 0:
            return {"status": "no_spot_balance"}
        _ = self.place_order(symbol=symbol, side="sell", order_type="market", qty=total_qty, reduce_only=False)
        return {"status": "closing_spot"}


