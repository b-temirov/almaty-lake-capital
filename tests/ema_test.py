import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(os.getcwd())

from bot.backtesting.backtester import Backtester
from bot.data.historical.binance_rest import BinanceRestClient
from bot.strategies.ema import EMAStrategy


ANNUALIZATION_FACTORS = {
    "1s": 365 * 24 * 60 * 60,
    "1m": 365 * 24 * 60,
    "3m": 365 * 24 * 20,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
    "30m": 365 * 24 * 2,
    "1h": 365 * 24,
    "2h": 365 * 12,
    "4h": 365 * 6,
    "6h": 365 * 4,
    "8h": 365 * 3,
    "12h": 365 * 2,
    "1d": 365,
}


def _parse_dataset_range(dataset: str):
    try:
        start_str, end_str = dataset.split("_", 1)
    except ValueError as exc:
        raise ValueError(
            "dataset must be in YYYY-MM-DD_YYYY-MM-DD format when using BinanceRestClient"
        ) from exc

    start_time = int(
        datetime.strptime(start_str, "%Y-%m-%d")
        .replace(tzinfo=timezone.utc)
        .timestamp()
        * 1000
    )
    end_time = int(
        datetime.strptime(end_str, "%Y-%m-%d")
        .replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        .timestamp()
        * 1000
    )
    return start_time, end_time


def load_rest_klines(symbol: str, interval: str, dataset: str):
    start_time, end_time = _parse_dataset_range(dataset)
    client = BinanceRestClient()
    return client.klines_df(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Backtest the EMA crossover strategy")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--freq", default="1m")
    parser.add_argument("--dataset", default="2026-01-11_2026-03-13")
    parser.add_argument("--fast-window", type=int, required=True)
    parser.add_argument("--slow-window", type=int, required=True)
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--output-csv")
    parser.add_argument("--plot_results")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.freq not in ANNUALIZATION_FACTORS:
        raise ValueError(f"Unsupported frequency for annualization: {args.freq}")

    data = load_rest_klines(
        symbol=args.symbol,
        interval=args.freq,
        dataset=args.dataset,
    )

    strategy = EMAStrategy(
        fast_window=args.fast_window,
        slow_window=args.slow_window,
    )
    backtester = Backtester(
        data=data,
        strategy=strategy,
        initial_capital=args.initial_capital,
        annualization_factor=ANNUALIZATION_FACTORS[args.freq],
    )
    results = backtester.run()

    if args.output_csv:
        output_path = Path(args.output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        backtester.data.to_csv(output_path, index=False)

    if args.plot_results:
        backtester.plot_results()

    signal_changes = backtester.data["signal"].diff().fillna(0)
    summary = {
        "symbol": args.symbol,
        "freq": args.freq,
        "dataset": args.dataset,
        "fast_window": args.fast_window,
        "slow_window": args.slow_window,
        "rows": int(len(backtester.data)),
        "bullish_crossovers": int((signal_changes == 1).sum()),
        "bearish_crossovers": int((signal_changes == -1).sum()),
        "active_signal_rows": int(backtester.data["signal"].sum()),
        "results": results,
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
