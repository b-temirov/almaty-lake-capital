import pandas as pd
import numpy as np
import glob
import os
import matplotlib.pyplot as plt
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DATA_ROOT = REPO_ROOT / 'bot' / 'data' / 'data' / 'spot' / 'daily' / 'klines' / 'BTCUSDT'

def calculate_market_events(price_series, l_bound, u_bound, rw):
    """
    Calculates bounce and penetration indices based on state-machine logic.
    """
    above, under, inside, wait = False, False, False, False
    bounce_indices = []
    pen_indices = []

    for index, price in price_series.items():
        if index < rw or pd.isna(u_bound[index]):
            continue

        if not above and not under and not inside:
            if price > u_bound[index]: above = True
            elif price < l_bound[index]: under = True
            elif l_bound[index] <= price <= u_bound[index]:
                inside, wait = True, True
        else:
            if not inside:
                if l_bound[index] <= price <= u_bound[index]:
                    inside = True
                elif price > u_bound[index]:
                    # if under: pen_indices.append(index)
                    above, under, inside = True, False, False
                elif price < l_bound[index]:
                    # if above: pen_indices.append(index)
                    under, above, inside = True, False, False
            else:
                if l_bound[index] <= price <= u_bound[index]:
                    continue
                elif wait:
                    wait = False
                    if price > u_bound[index]: above, under, inside = True, False, False
                    elif price < l_bound[index]: under, above, inside = True, False, False
                else:
                    if price > u_bound[index]:
                        if above: bounce_indices.append(index)
                        elif under: pen_indices.append(index)
                        above, under, inside = True, False, False
                    elif price < l_bound[index]:
                        # if under: bounce_indices.append(index)
                        # elif above: pen_indices.append(index)
                        under, above, inside = True, False, False
    return bounce_indices, pen_indices

def main(freq, atr):
    # Configuration
    # atr = 200
    # path = f'bot/data/data/spot/daily/klines/BTCUSDT/{freq}/2026-02-12_2026-03-12/'
    path = DATA_ROOT / freq / '2026-02-12_2026-03-12'

    all_files = glob.glob(os.path.join(path, "*.csv"))
    cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 
            'taker_buy_quote_asset_volume', 'ignore']

    # Data Loading
    df_list = [pd.read_csv(f, header=None, names=cols) for f in all_files]
    df = pd.concat(df_list, ignore_index=True)
    df = df.sort_values('open_time').reset_index(drop=True)

    # Analysis loop
    results = []
    windows = range(2, 500)

    for rw in windows:
        ma = df['close'].rolling(window=rw).mean()
        l_bound = ma - atr * 0.5
        u_bound = ma + atr * 0.5

        b_idx, p_idx = calculate_market_events(df['close'], l_bound, u_bound, rw)

        results.append({
            'Rolling_Window': rw,
            'Bounces': len(b_idx),
            'Penetrations': len(p_idx)
        })

    stats_df = pd.DataFrame(results)
    stats_df['total'] = stats_df['Bounces'] + stats_df['Penetrations']
    stats_df['bounce_perc'] = (stats_df['Bounces'] / stats_df['total'] * 100).fillna(0)

    # Create a figure with 1 row and 2 columns
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # Subplot 1: Bounce Percentage
    ax1.plot(stats_df['Rolling_Window'], stats_df['bounce_perc'], color='green', marker='o')
    ax1.set_title(f'Bounce Percentage vs Rolling Window (ATR={atr})')
    ax1.set_xlabel('Rolling Window (rw)')
    ax1.set_ylabel('Percentage (%)')
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Total Interactions
    ax2.plot(stats_df['Rolling_Window'], stats_df['total'], label='Interactions', marker='o', color='green')
    # ax2.plot(stats_comparison_df['Rolling_Window'], stats_comparison_df['Penetrations'], label='Penetrations', marker='x', color='red')
    ax2.set_title(f'# of Interactions (ATR={atr})')
    ax2.set_xlabel('Rolling Window (rw)')
    ax2.set_ylabel('# of interactions')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Adjust layout to prevent overlapping labels
    plt.tight_layout()
    # plt.show()

    # Define the directory path
    # figure_dir = Path(f'./bot/strategy/discovery/figures/{atr}')
    figure_dir = SCRIPT_DIR / 'figures' / str(atr)

    # Create the folder if it doesn't exist (parents=True creates figures/ if missing too)
    figure_dir.mkdir(parents=True, exist_ok=True)

    # Save the plot
    plt.savefig(fname=figure_dir / f'{freq}_bounce_percentage.png')

    # data_dir = Path(f'./bot/strategy/discovery/data/{atr}')
    data_dir = SCRIPT_DIR / 'data' / str(atr)

    data_dir.mkdir(parents=True, exist_ok=True)
    
    stats_df.to_csv(data_dir / f'{freq}_bounce_data.csv')

if __name__ == "__main__":
    freqs = ['1d', '12h', '8h', '6h', '4h', '2h', '1h', '30m', '15m', '5m', '3m', '1m']
    atrs = [i for i in range(50, 1000, 50)]
    for atr in atrs:
        for freq in freqs:
            main(freq, atr)
