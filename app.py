import os
import time
from datetime import datetime, timedelta
from flask import Flask
from kiteconnect import KiteConnect
import pandas as pd

app = Flask(__name__)

API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")

@app.route("/")
def run_backtest_web():
    if not API_KEY or not ACCESS_TOKEN:
        return "<h3>Setup Error: KITE_API_KEY or KITE_ACCESS_TOKEN environment variables are missing!</h3>"

    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(ACCESS_TOKEN)

        # DYNAMIC DATES: Automatically calculate exactly 365 days back from TODAY
        final_end_date = datetime.now().date()
        final_start_date = final_end_date - timedelta(days=365)

        all_chunks = []
        current_start = final_start_date

        while current_start < final_end_date:
            current_end = min(current_start + timedelta(days=90), final_end_date)
            try:
                data = kite.historical_data(
                    instrument_token=265, # SENSEX Instrument Token
                    from_date=current_start.strftime("%Y-%m-%d"),
                    to_date=current_end.strftime("%Y-%m-%d"),
                    interval="5minute",
                )
                if data:
                    all_chunks.extend(data)
                time.sleep(0.6) # Slightly safer delay to avoid Kite rate limits
            except Exception as e:
                return f"<h3>Kite API Error during data fetch: {e}</h3><p>Dates attempted: {current_start} to {current_end}</p>"
            
            current_start = current_end + timedelta(days=1)

        if not all_chunks:
            return f"<h3>Error: No historical data retrieved. Your account might be missing active Historical Data API access.</h3>"

        df = pd.DataFrame(all_chunks)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # --- CALCULATE STRATEGY INDICATORS ---
        df["EMA9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["EMA21"] = df["close"].ewm(span=21, adjust=False).mean()
        df["date_only"] = df["date"].dt.date
        df["cum_volume"] = df.groupby("date_only")["volume"].cumsum()
        df["cum_vol_price"] = (df["close"] * df["volume"]).groupby(df["date_only"]).cumsum()
        df["VWAP"] = df["cum_vol_price"] / df["cum_volume"]
        df["prev_EMA9"] = df["EMA9"].shift(1)
        df["prev_EMA21"] = df["EMA21"].shift(1)

        # Filter Intraday Trading Hours (09:20 to 14:30)
        df["time"] = df["date"].dt.time
        market_start = datetime.strptime("09:20", "%H:%M").time()
        market_end = datetime.strptime("14:30", "%H:%M").time()
        df = df[(df["time"] >= market_start) & (df["time"] <= market_end)].copy()

        if df.empty:
            return "<h3>Data Processing Error: Filtered intraday dataset is empty. Check your chart intervals.</h3>"

        # --- RUN ENGINE ---
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
                    current_position = "BUY"; entry_price = close; entry_time = row["date"]
                elif is_sell_signal:
                    current_position = "SELL"; entry_price = close; entry_time = row["date"]
            elif current_position == "BUY" and is_sell_signal:
                pnl = close - entry_price
                trades.append({"Type": "BUY", "PnL": pnl, "Return %": (pnl/entry_price)*100})
                current_position = "SELL"; entry_price = close; entry_time = row["date"]
            elif current_position == "SELL" and is_buy_signal:
                pnl = entry_price - close
                trades.append({"Type": "SELL", "PnL": pnl, "Return %": (pnl/entry_price)*100})
                current_position = "BUY"; entry_price = close; entry_time = row["date"]

        trades_df = pd.DataFrame(trades)

        if not trades_df.empty:
            total_trades = len(trades_df)
            winning_trades = len(trades_df[trades_df["PnL"] > 0])
            win_rate = (winning_trades / total_trades) * 100
            total_return = trades_df["Return %"].sum()

            return f"""
            <div style="font-family: sans-serif; padding: 30px; max-width: 600px; margin: auto; border: 1px solid #ccc; border-radius: 10px; box-shadow: 2px 2px 12px #eee;">
                <h2 style="color: #2c3e50; text-align: center;">📊 SENSEX 1-Year Backtest Results</h2>
                <hr style="border: 0; border-top: 1px solid #eee;">
                <p style="font-size: 16px;"><b>Backtest Period:</b> {final_start_date} to {final_end_date}</p>
                <p style="font-size: 16px;"><b>Total Trades Executed:</b> {total_trades}</p>
                <p style="font-size: 16px;"><b>Winning Trades:</b> {winning_trades}</p>
                <p style="font-size: 16px; color: #27ae60;"><b>Strategy Win Rate:</b> {win_rate:.2f}%</p>
                <h3 style="background-color: #f8f9fa; padding: 15px; text-align: center; border-radius: 5px; color: #2980b9;">
                    Cumulative Return: {total_return:.2f}%
                </h3>
            </div>
            """
        return "<h3>Execution completed cleanly, but no entry signals triggered across this timeline framework.</h3>"

    except Exception as global_err:
        return f"<h3>Critical Application Crash: {global_err}</h3>"

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
