import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

from bot.data.historical.binance_rest import INTERVAL_TO_MS
from bot.data.historical.binance_rest import BinanceRestClient
from bot.data.streaming.binance_ws import BinanceWebSocketClient
from bot.execution.roostoo_client import RoostooClient
from bot.logging_config import setup_logging
from bot.strategies.ema import EMAStrategy


logger = logging.getLogger(__name__)


@dataclass
class PortfolioState:
    cash_usd: float
    asset_quantity: float = 0.0
    entry_price: float = 0.0
    realized_pnl: float = 0.0


def _load_initial_history(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    rest_client = BinanceRestClient()
    history = rest_client.klines_df(symbol=symbol, interval=interval, limit=limit)
    if history.empty:
        raise ValueError("Unable to bootstrap live EMA strategy with empty history")
    return history.sort_values("open_time").reset_index(drop=True)


def _interval_ms(interval: str) -> int:
    if interval not in INTERVAL_TO_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_TO_MS[interval]


def _derive_trade_quantity(notional_usd: float, last_price: float) -> float:
    if last_price <= 0:
        raise ValueError("last_price must be positive")
    return notional_usd / last_price


def _fetch_missing_history(
    rest_client: BinanceRestClient,
    symbol: str,
    interval: str,
    previous_open_time: pd.Timestamp,
    next_open_time: pd.Timestamp,
) -> pd.DataFrame:
    interval_delta_ms = _interval_ms(interval)
    expected_next_open_time = previous_open_time + pd.Timedelta(milliseconds=interval_delta_ms)

    if next_open_time <= expected_next_open_time:
        return pd.DataFrame()

    missing_until = next_open_time - pd.Timedelta(milliseconds=interval_delta_ms)
    missing_history = rest_client.klines_df(
        symbol=symbol,
        interval=interval,
        limit=1000,
        start_time=int(expected_next_open_time.timestamp() * 1000),
        end_time=int(missing_until.timestamp() * 1000),
    )
    return missing_history


def _normalize_order_quantity(
    coin: str,
    quantity: float,
    execution_client: Optional[RoostooClient],
) -> float:
    if execution_client is not None:
        return execution_client.round_quantity(coin, quantity)

    hardcoded_amount_precision = {
        "BTC": 5,
    }
    precision = hardcoded_amount_precision.get(coin.upper())
    if precision is None:
        return quantity

    return round(quantity, precision)


def _buy_position(
    *,
    symbol: str,
    coin: str,
    latest_close: float,
    trade_notional_usd: float,
    portfolio: PortfolioState,
    execution_client: Optional[RoostooClient],
    dry_run: bool,
) -> bool:
    buy_notional_usd = min(trade_notional_usd, portfolio.cash_usd)
    if buy_notional_usd <= 0:
        logger.warning("No cash available for a new buy.")
        return False

    trade_quantity = _derive_trade_quantity(
        notional_usd=buy_notional_usd,
        last_price=latest_close,
    )
    trade_quantity = _normalize_order_quantity(
        coin=coin,
        quantity=trade_quantity,
        execution_client=execution_client,
    )
    if trade_quantity <= 0:
        logger.warning("Rounded buy quantity became zero. Skipping buy.")
        return False

    if dry_run:
        logger.info(
            "DRY RUN buy signal symbol=%s quantity=%.8f notional_usd=%.2f close=%s",
            symbol,
            trade_quantity,
            buy_notional_usd,
            latest_close,
        )
    else:
        order_result = execution_client.market_buy(  # type: ignore
            coin=coin, quantity=trade_quantity
        )
        logger.info("BUY order placed result=%s", order_result)

    portfolio.cash_usd -= buy_notional_usd
    portfolio.asset_quantity = trade_quantity
    portfolio.entry_price = latest_close
    return True


def _portfolio_snapshot(portfolio: PortfolioState, last_price: float):
    position_value = portfolio.asset_quantity * last_price
    unrealized_pnl = 0.0

    if portfolio.asset_quantity > 0 and portfolio.entry_price > 0:
        unrealized_pnl = (last_price - portfolio.entry_price) * portfolio.asset_quantity

    total_equity = portfolio.cash_usd + position_value
    total_pnl = portfolio.realized_pnl + unrealized_pnl

    return {
        "position_value": position_value,
        "unrealized_pnl": unrealized_pnl,
        "total_equity": total_equity,
        "total_pnl": total_pnl,
    }


def _log_portfolio_state(
    portfolio: PortfolioState,
    last_price: float,
    allocated_capital_usd: float,
):
    snapshot = _portfolio_snapshot(portfolio, last_price)
    logger.info(
        "Portfolio status price=%.2f cash=%.2f qty=%.8f entry=%.2f equity=%.2f realized_pnl=%.2f unrealized_pnl=%.2f total_pnl=%.2f return_pct=%.2f%%",
        last_price,
        portfolio.cash_usd,
        portfolio.asset_quantity,
        portfolio.entry_price,
        snapshot["total_equity"],
        portfolio.realized_pnl,
        snapshot["unrealized_pnl"],
        snapshot["total_pnl"],
        (snapshot["total_pnl"] / allocated_capital_usd) * 100,
    )


def run_live_ema_session(
    symbol: str = "BTCUSDT",
    coin: str = "BTC",
    interval: str = "1m",
    runtime_minutes: int = 10,
    fast_window: int = 20,
    slow_window: int = 40,
    warmup_limit: int = 200,
    allocated_capital_usd: float = 1000.0,
    trade_notional_usd: float = 100.0,
    dry_run: bool = True,
):
    if runtime_minutes <= 0:
        raise ValueError("runtime_minutes must be positive")
    if allocated_capital_usd <= 0:
        raise ValueError("allocated_capital_usd must be positive")
    if trade_notional_usd <= 0:
        raise ValueError("trade_notional_usd must be positive")
    if warmup_limit < slow_window:
        raise ValueError("warmup_limit must be at least slow_window")

    load_dotenv()
    setup_logging()

    rest_client = BinanceRestClient()
    market_history = _load_initial_history(
        symbol=symbol,
        interval=interval,
        limit=warmup_limit,
    )
    ws_client = BinanceWebSocketClient()
    strategy = EMAStrategy(fast_window=fast_window, slow_window=slow_window)

    execution_client = None
    if not dry_run:
        execution_client = RoostooClient(
            api_key=os.environ["ROOSTOO_API_KEY"],
            secret_key=os.environ["ROOSTOO_SECRET_KEY"],
        )

    session_started_at = datetime.now(timezone.utc)
    session_deadline = time.time() + runtime_minutes * 60
    last_processed_open_time = market_history["open_time"].iloc[-1]
    last_signal = None
    current_position = 0
    portfolio = PortfolioState(cash_usd=allocated_capital_usd)

    seeded_signals = strategy.generate_signals(market_history)
    if not seeded_signals.empty:
        last_signal = int(seeded_signals["signal"].iloc[-1])
        latest_seeded_close = float(seeded_signals["close"].iloc[-1])

    logger.info(
        "Starting live EMA session symbol=%s interval=%s runtime_minutes=%s dry_run=%s start_time=%s initial_signal=%s allocated_capital_usd=%.2f trade_notional_usd=%.2f",
        symbol,
        interval,
        runtime_minutes,
        dry_run,
        session_started_at.isoformat(),
        last_signal,
        allocated_capital_usd,
        trade_notional_usd,
    )

    if last_signal == 1 and current_position == 0:
        logger.info(
            "Initial seeded signal is bullish. Entering position immediately at close=%s",
            latest_seeded_close,
        )
        if _buy_position(
            symbol=symbol,
            coin=coin,
            latest_close=latest_seeded_close,
            trade_notional_usd=trade_notional_usd,
            portfolio=portfolio,
            execution_client=execution_client,
            dry_run=dry_run,
        ):
            current_position = 1

    for candle_df in ws_client.stream_klines_df(
        symbol=symbol,
        interval=interval,
        closed_only=True,
    ):
        if time.time() >= session_deadline:
            logger.info("Live EMA session reached runtime limit. Exiting.")
            break

        candle_open_time = candle_df["open_time"].iloc[0]
        if candle_open_time <= last_processed_open_time:
            continue

        missing_history = _fetch_missing_history(
            rest_client=rest_client,
            symbol=symbol,
            interval=interval,
            previous_open_time=last_processed_open_time,
            next_open_time=candle_open_time,
        )
        if not missing_history.empty:
            logger.warning(
                "Backfilled missing candles symbol=%s interval=%s missing_count=%s from_open_time=%s to_open_time=%s",
                symbol,
                interval,
                len(missing_history),
                missing_history["open_time"].iloc[0],
                missing_history["open_time"].iloc[-1],
            )

        market_history = pd.concat(
            [market_history, missing_history, candle_df],
            ignore_index=True,
        )
        market_history = (
            market_history.drop_duplicates(subset=["open_time"])
            .sort_values("open_time")
            .tail(warmup_limit)
            .reset_index(drop=True)
        )

        signal_df = strategy.generate_signals(market_history)
        latest_row = signal_df.iloc[-1]
        latest_signal = int(latest_row["signal"])
        latest_close = float(latest_row["close"])

        logger.info(
            "Closed candle received symbol=%s open_time=%s close=%s ema_fast=%.4f ema_slow=%.4f signal=%s",
            symbol,
            latest_row["open_time"],
            latest_close,
            float(latest_row["ema_fast"]),
            float(latest_row["ema_slow"]),
            latest_signal,
        )
        _log_portfolio_state(portfolio, latest_close, allocated_capital_usd)

        if last_signal is None:
            last_signal = latest_signal
            last_processed_open_time = candle_open_time
            continue

        if latest_signal == last_signal:
            logger.info(
                "No signal change symbol=%s signal=%s position=%s",
                symbol,
                latest_signal,
                current_position,
            )
            last_processed_open_time = candle_open_time
            continue

        if latest_signal == 1 and current_position == 0:
            if _buy_position(
                symbol=symbol,
                coin=coin,
                latest_close=latest_close,
                trade_notional_usd=trade_notional_usd,
                portfolio=portfolio,
                execution_client=execution_client,
                dry_run=dry_run,
            ):
                current_position = 1
            else:
                logger.warning("Unable to enter long position. Stopping session.")
                break

        elif latest_signal == 0 and current_position == 1:
            trade_quantity = _normalize_order_quantity(
                coin=coin,
                quantity=portfolio.asset_quantity,
                execution_client=execution_client,
            )
            if trade_quantity <= 0:
                logger.warning("Rounded sell quantity became zero. Skipping sell.")
                last_signal = latest_signal
                last_processed_open_time = candle_open_time
                continue
            sell_notional_usd = trade_quantity * latest_close

            if dry_run:
                logger.info(
                    "DRY RUN sell signal symbol=%s quantity=%.8f notional_usd=%.2f close=%s",
                    symbol,
                    trade_quantity,
                    sell_notional_usd,
                    latest_close,
                )
            else:
                order_result = execution_client.market_sell(  # type: ignore
                    coin=coin, quantity=trade_quantity
                )
                logger.info("SELL order placed result=%s", order_result)

            cost_basis = trade_quantity * portfolio.entry_price
            portfolio.cash_usd += sell_notional_usd
            portfolio.realized_pnl += sell_notional_usd - cost_basis
            portfolio.asset_quantity = 0.0
            portfolio.entry_price = 0.0
            current_position = 0

        else:
            logger.info(
                "Signal changed but no action taken symbol=%s signal=%s position=%s",
                symbol,
                latest_signal,
                current_position,
            )

        last_signal = latest_signal
        last_processed_open_time = candle_open_time

        snapshot = _portfolio_snapshot(portfolio, latest_close)
        if snapshot["total_equity"] <= 0:
            logger.warning("Allocated capital has been exhausted. Stopping session.")
            break

    logger.info(
        "Live EMA session completed symbol=%s runtime_minutes=%s final_position=%s final_cash=%.2f final_qty=%.8f realized_pnl=%.2f",
        symbol,
        runtime_minutes,
        current_position,
        portfolio.cash_usd,
        portfolio.asset_quantity,
        portfolio.realized_pnl,
    )


if __name__ == "__main__":
    run_live_ema_session(
        runtime_minutes=240,
        allocated_capital_usd=1000,
        trade_notional_usd=100,
        dry_run=False,
    )
