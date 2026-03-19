import argparse
import glob
import json
import os
from pathlib import Path

import pandas as pd

from bot.backtesting.backtester import Backtester
from bot.strategies.bounce_slope import BounceSlopeStrategy


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DATA_ROOT = REPO_ROOT / "bot" / "data" / "data" / "spot" / "daily" / "klines"

KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]

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


def load_local_klines(symbol: str, interval: str, dataset: str) -> pd.DataFrame:
    path = DATA_ROOT / symbol / interval / dataset
    files = sorted(glob.glob(os.path.join(path, "*.csv")))
    if not files:
        raise FileNotFoundError(f"No CSV files found under {path}")

    df_list = [pd.read_csv(file_path, header=None, names=KLINE_COLUMNS) for file_path in files]
    data = pd.concat(df_list, ignore_index=True)
    data = data.sort_values("open_time").reset_index(drop=True)
    data["open_time"] = pd.to_datetime(data["open_time"], unit="ms", utc=True)
    data["close_time"] = pd.to_datetime(data["close_time"], unit="ms", utc=True)
    return data


def parse_args():
    parser = argparse.ArgumentParser(description="Backtest the slope-filtered bounce strategy")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--freq", default="1m")
    parser.add_argument("--dataset", default="2026-02-12_2026-03-12")
    parser.add_argument("--rolling-window", type=int, required=True)
    parser.add_argument("--atr", type=float, required=True)
    parser.add_argument("--slope-window", type=int, default=75)
    parser.add_argument("--hold-periods", type=int, default=1)
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--output-csv")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.freq not in ANNUALIZATION_FACTORS:
        raise ValueError(f"Unsupported frequency for annualization: {args.freq}")

    data = load_local_klines(
        symbol=args.symbol,
        interval=args.freq,
        dataset=args.dataset,
    )

    strategy = BounceSlopeStrategy(
        rolling_window=args.rolling_window,
        atr=args.atr,
        slope_window=args.slope_window,
        hold_periods=args.hold_periods,
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

    summary = {
        "symbol": args.symbol,
        "freq": args.freq,
        "dataset": args.dataset,
        "rolling_window": args.rolling_window,
        "atr": args.atr,
        "slope_window": args.slope_window,
        "hold_periods": args.hold_periods,
        "rows": int(len(backtester.data)),
        "bounce_events": int(backtester.data["bounce_event"].sum()),
        "pen_events": int(backtester.data["pen_event"].sum()),
        "active_signal_rows": int(backtester.data["signal"].sum()),
        "results": results,
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
