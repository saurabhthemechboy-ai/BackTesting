from datetime import datetime, timedelta
import os
import time
from kiteconnect import KiteConnect
import pandas as pd

# --- 1. SETUP KITE CLIENT ---
API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = "f3yAMI1PMBgORimWDAQS0ViEGk4WmT36"

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

# --- 2. DEFINE CHUNK-BASED DATE RANGE ---
# Setting up a full 365-day window ending today (May 21, 2026)
final_end_date = datetime.strptime("2026-05-21", "%Y-%m-%d").date()
final_start_date = final_end_date - timedelta(days=365)

instrument_token = 265
interval = "5minute"

all_chunks = []
current_start = final_start_date

print(f"Initiating 1-year backtest data pull from {final_start_date} to {final_end_date}...")

# Loop to fetch data in maximum 90-day increments
while current_start < final_end_date:
    current_end = min(current_start + timedelta(days=90), final_end_date)
    
    print(f"Fetching chunk: {current_start} to {current_end}")
    try:
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=current_start.strftime("%Y-%m-%d"),
            to_date=current_end.strftime("%Y-%m-%d"),
            interval=interval,
        )
        if data:
            all_chunks.extend(data)
            
        # Polite 0.5-second pause to remain well within Kite API rate limits
        time.sleep(0.5)
        
    except Exception as e:
        print(f"Error fetching data for segment {current_start} to {current_end}: {e}")
        break
        
    # Move the window forward for the next iteration
    current_start = current_end + timedelta(days=1)

# Combine all retrieved data chunks
if not all_chunks:
    print("No historical data retrieved. Ending execution.")
    exit()

df = pd.DataFrame(all_chunks)
df["date"] = pd.to_datetime(df["date"])
# Sort chronologically to make sure indicators compute correctly
df = df.sort_values("date").reset_index(drop=True)
print(f"Successfully loaded {len(df)} continuous data points.")


# --- 3. CALCULATE INDICATORS ---
print("Calculating strategy indicators...")
df["EMA9"] = df["close"].ewm(span=9, adjust=False).mean()
df["EMA21"] = df["close"].ewm(span=21, adjust=False).mean()

# VWAP calculates cleanly per calendar day
df["date_only"] = df["date"].dt.date
df["cum_volume"] = df.groupby("date_only")["volume"].cumsum()

# Use transform to preserve the exact indexing framework for inline math
df["cum_vol_price"] = (df["close"] * df["volume"]).groupby(df["date_only"]).cumsum()
df["VWAP"] = df["cum_vol_price"] / df["cum_volume"]

# Pull the previous candle values for clear crossover tracking
df["prev_EMA9"] = df["EMA9"].shift(1)
df["prev_EMA21"] = df["EMA21"].shift(1)


# --- 4. FILTER INTRA-DAY TRADING HOURS (09:20 - 14:30) ---
df["time"] = df["date"].dt.time
market_start = datetime.strptime("09:20", "%H:%M").time()
market_end = datetime.strptime("14:30", "%H:%M").time()
df = df[(df["time"] >= market_start) & (df["time"] <= market_end)].copy()


# --- 5. RUN BACKTEST ENGINE ---
print("Simulating trades across historical timeline...")
trades = []
current_position = None  
entry_price = 0
entry_time = None

for i in range(1, len(df)):
    row = df.iloc[i]

    close = row["close"]
    vwap = row["VWAP"]
    ema9, ema21 = row["EMA9"], row["EMA21"]
    p_ema9, p_ema21 = row["prev_EMA9"], row["prev_EMA21"]

    is_buy_signal = p_ema9 < p_ema21 and ema9 > ema21 and close > vwap
    is_sell_signal = p_ema9 > p_ema21 and ema9 < ema21 and close < vwap

    if current_position is None:
        if is_buy_signal:
            current_position = "BUY"
            entry_price = close
            entry_time = row["date"]
        elif is_sell_signal:
            current_position = "SELL"
            entry_price = close
            entry_time = row["date"]

    elif current_position == "BUY" and is_sell_signal:
        pnl = close - entry_price
        pct_return = (pnl / entry_price) * 100
        trades.append({
            "Type": "BUY",
            "Entry Time": entry_time,
            "Exit Time": row["date"],
            "Entry": entry_price,
            "Exit": close,
            "PnL": pnl,
            "Return %": pct_return,
        })
        current_position = "SELL"
        entry_price = close
        entry_time = row["date"]

    elif current_position == "SELL" and is_buy_signal:
        pnl = entry_price - close  
        pct_return = (pnl / entry_price) * 100
        trades.append({
            "Type": "SELL",
            "Entry Time": entry_time,
            "Exit Time": row["date"],
            "Entry": entry_price,
            "Exit": close,
            "PnL": pnl,
            "Return %": pct_return,
        })
        current_position = "BUY"
        entry_price = close
        entry_time = row["date"]

# --- 6. METRICS & ANALYSIS ---
trades_df = pd.DataFrame(trades)

if not trades_df.empty:
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df["PnL"] > 0])
    win_rate = (winning_trades / total_trades) * 100
    total_return = trades_df["Return %"].sum()
    
    # Calculate performance splits
    avg_trade = trades_df["Return %"].mean()
    max_win = trades_df["Return %"].max()
    max_loss = trades_df["Return %"].min()

    print("\n" + "=" * 40)
    print("         1-YEAR STRATEGY SUMMARY        ")
    print("=" * 40)
    print(f"Total Period Checked  : {final_start_date} to {final_end_date}")
    print(f"Total Trades Executed : {total_trades}")
    print(f"Winning Trades        : {winning_trades}")
    print(f"Strategy Win Rate     : {win_rate:.2f}%")
    print(f"Cumulative Return     : {total_return:.2f}%")
    print(f"Average Return/Trade  : {avg_trade:.2f}%")
    print(f"Best Trade Performance: {max_win:.2f}%")
    print(f"Worst Trade Drawdown  : {max_loss:.2f}%")
    print("=" * 40)
else:
    print("\nNo historical signals triggered across this timeline.")
