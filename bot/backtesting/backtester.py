import numpy as np


class CryptoStrategy:
    """Base class for trading strategies."""

    def generate_signals(self, df):
        raise NotImplementedError("Subclasses must implement generate_signals")


class Backtester:
    def __init__(
        self,
        data,
        strategy,
        initial_capital=10000,
        risk_free_rate=0.0,
        annualization_factor=365,
    ):
        self.data = data.copy()
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor
        self.results = None

    def run(self):
        # 1. Generate signals
        self.data = self.strategy.generate_signals(self.data)

        # 2. Calculate Returns
        self.data["returns"] = self.data["close"].pct_change()
        self.data["strategy_returns"] = self.data["returns"] * self.data[
            "signal"
        ].shift(1)

        # 3. Equity Curve
        self.data["equity_curve"] = (
            1 + self.data["strategy_returns"].fillna(0)
        ).cumprod() * self.initial_capital
        return self.calculate_metrics()

    def calculate_metrics(self):
        returns = self.data["strategy_returns"].dropna()
        ann_factor = self.annualization_factor
        mean_ret = returns.mean() * ann_factor
        std_ret = returns.std() * np.sqrt(ann_factor)

        sharpe = (mean_ret - self.risk_free_rate) / std_ret if std_ret > 0 else 0

        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std() * np.sqrt(ann_factor)
            sortino = (
                (mean_ret - self.risk_free_rate) / downside_std
                if downside_std > 0
                else 0
            )
        else:
            sortino = mean_ret / 1e-6 if mean_ret > 0 else 0

        peak = self.data["equity_curve"].cummax()
        self.data["drawdown"] = (self.data["equity_curve"] - peak) / peak
        max_drawdown = abs(self.data["drawdown"].min())
        calmar = mean_ret / max_drawdown if max_drawdown > 0 else 0

        self.results = {
            "Total Return": (self.data["equity_curve"].iloc[-1] / self.initial_capital)
            - 1,
            "Sharpe Ratio": sharpe,
            "Sortino Ratio": sortino,
            "Calmar Ratio": calmar,
            "Max Drawdown": max_drawdown,
        }
        return self.results

    # def plot_results(self):
    #     if self.results is None:
    #         print("Run the backtester first.")
    #         return
    #     if plt is None:
    #         print("matplotlib is not installed. Plotting is unavailable.")
    #         return

    #     fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1]})

    #     # Plot Equity Curve
    #     ax1.plot(self.data['open_time'], self.data['equity_curve'], label='Strategy Equity', color='blue')
    #     ax1.set_title('Strategy Equity Curve')
    #     ax1.set_ylabel('Capital ($)')
    #     ax1.grid(True)
    #     ax1.legend()

    #     # Plot Drawdown
    #     ax2.fill_between(self.data['open_time'], self.data['drawdown'], 0, color='red', alpha=0.3, label='Drawdown')
    #     ax2.set_title('Underwater Plot (Drawdown)')
    #     ax2.set_ylabel('Drawdown %')
    #     ax2.set_xlabel('Time')
    #     ax2.grid(True)

    #     plt.tight_layout()
    #     plt.show()
