import os
import time
from datetime import datetime, timedelta
from flask import Flask
from kiteconnect import KiteConnect
import pandas as pd

app = Flask(__name__)

# Strip any accidental white spaces or quotes from Render's panel
API_KEY = os.getenv("KITE_API_KEY", "").strip().replace('"', '').replace("'", "")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "").strip().replace('"', '').replace("'", "")

@app.route("/")
def run_backtest_web():
    if not API_KEY or not ACCESS_TOKEN:
        return f"""
        <div style="font-family:sans-serif; padding:20px; color:#c0392b;">
            <h3>❌ Configuration Error</h3>
            <p>Render environment variables are empty or missing!</p>
            <p><b>Detected API Key length:</b> {len(API_KEY)} characters</p>
            <p><b>Detected Access Token length:</b> {len(ACCESS_TOKEN)} characters</p>
        </div>
        """

    try:
        # Initialize client framework wrapper
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(ACCESS_TOKEN)

        # PRE-FLIGHT AUTHENTICATION TEST
        try:
            profile = kite.profile()
            user_name = profile.get("user_name", "Valued Trader")
        except Exception as auth_err:
            return f"""
            <div style="font-family:sans-serif; padding:30px; border:1px solid #f5c6cb; background-color:#f8d7da; color:#721c24; border-radius:5px; max-width:600px; margin:20px auto;">
                <h3 style="margin-top:0;">❌ Zerodha Authentication Rejected</h3>
                <p>Your <b>KITE_API_KEY</b> or <b>KITE_ACCESS_TOKEN</b> was rejected by Zerodha's login servers.</p>
                <p><b>Error Details:</b> <code style="background:#fff; padding:2px 5px; border-radius:3px;">{auth_err}</code></p>
                <hr style="border:0; border-top:1px solid #f5c6cb;">
                <h4>💡 Debug Checklist:</h4>
                <ol style="padding-left:20px;">
                    <li>Did you reset your <b>API Secret</b> on the developer portal? If yes, your active access token was permanently killed. You must log in via your browser again to generate a new one.</li>
                    <li>Double check that you didn't paste your <b>API Secret</b> inside the <b>API Key</b> slot on Render.</li>
                    <li>Ensure your session token hasn't expired.</li>
                </ol>
            </div>
            """

        # Calculate time windows dynamically
        final_end_date = datetime.now().date()
        final_start_date = final_end_date - timedelta(days=365)

        all_chunks = []
        current_start = final_start_date

        # Sequential Data Fetching Loop
        while current_start < final_end_date:
            current_end = min(current_start + timedelta(days=90), final_end_date)
            str_start = current_start.strftime("%Y-%m-%d")
            str_end = current_end.strftime("%Y-%m-%d")
            
            try:
                # Ordered positional arguments targeting SENSEX (Token: 265)
                data = kite.historical_data(265, str_start, str_end, "5minute")
                if data:
                    all_chunks.extend(data)
                time.sleep(0.6)
            except Exception as loop_error:
                return f"""
                <div style="font-family:sans-serif; padding:20px;">
                    <h3>⚠️ Account Active but Data Fetch Rejected</h3>
                    <p>Logged in successfully as <b>{user_name}</b>, but historical charts were blocked.</p>
                    <p><b>Reason:</b> <span style="color:red;">{loop_error}</span></p>
                    <p><i>Note: If it says 'insufficient permission', you need to renew your base ₹500 plan or clear your app cache.</i></p>
                </div>
                """
            current_start = current_end + timedelta(days=1)

        if not all_chunks:
            return "<h3>Error: Zerodha servers returned an empty dataset block.</h3>"

        # --- DATA PROCESSING FRAMEWORK ---
        df = pd.DataFrame(all_chunks)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        df["close"] = pd.to_numeric(df["close"], errors='coerce')
        df["volume"] = pd.to_numeric(df["volume"], errors='coerce').fillna(0)

        # Indicator Calculations
        df["EMA9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["EMA21"] = df["close"].ewm(span=21, adjust=False).mean()
        
        df["date_only"] = df["date"].dt.date
        df["vol_price"] = df["close"] * df["volume"]
        df["cum_volume"] = df.groupby("date_only")["volume"].cumsum()
        df["cum_vol_price"] = df.groupby("date_only")["vol_price"].cumsum()
        df["VWAP"] = df["cum_vol_price"] / df["cum_volume"]
        df["VWAP"] = df["VWAP"].fillna(df["close"]) 
        
        df["prev_EMA9"] = df["EMA9"].shift(1)
        df["prev_EMA21"] = df["EMA21"].shift(1)

        # Filter Intraday Trading Hours (09:20 to 14:30)
        df["time"] = df["date"].dt.time
        market_start = datetime.strptime("09:20", "%H:%M").time()
        market_end = datetime.strptime("14:30", "%H:%M").time()
        df = df[(df["time"] >= market_start) & (df["time"] <= market_end)].copy()

        # --- RUN BACKTEST ENGINE ---
        trades = []
        current_position = None
        entry_price = 0

        for i in range(1, len(df)):
            row = df.iloc[i]
            close = row["close"]
            vwap = row["VWAP"]
            ema9, ema21 = row["EMA9"], row["EMA21"]
            p_ema9, p_ema21 = row["prev_EMA9"], row["prev_EMA21"]

            if pd.isna(p_ema9) or pd.isna(p_ema21):
                continue

            is_buy_signal = p_ema9 < p_ema21 and ema9 > ema21 and close > vwap
            is_sell_signal = p_ema9 > p_ema21 and ema9 < ema21 and close < vwap

            if current_position is None:
                if is_buy_signal: current_position = "BUY"; entry_price = close
                elif is_sell_signal: current_position = "SELL"; entry_price = close
            elif current_position == "BUY" and is_sell_signal:
                pnl = close - entry_price
                trades.append({"Type": "BUY", "PnL": pnl, "Return %": (pnl/entry_price)*100})
                current_position = "SELL"; entry_price = close
            elif current_position == "SELL" and is_buy_signal:
                pnl = entry_price - close
                trades.append({"Type": "SELL", "PnL": pnl, "Return %": (pnl/entry_price)*100})
                current_position = "BUY"; entry_price = close

        trades_df = pd.DataFrame(trades)

        if not trades_df.empty:
            total_trades = len(trades_df)
            winning_trades = len(trades_df[trades_df["PnL"] > 0])
            win_rate = (winning_trades / total_trades) * 100
            total_return = trades_df["Return %"].sum()

            return f"""
            <div style="font-family: sans-serif; padding: 30px; max-width: 600px; margin: auto; border: 1px solid #ccc; border-radius: 10px; box-shadow: 2px 2px 12px #eee; background-color:#fff;">
                <h2 style="color: #2c3e50; text-align: center;">📊 SENSEX 1-Year Backtest Results</h2>
                <hr style="border: 0; border-top: 1px solid #eee;">
                <p style="font-size: 16px;"><b>Trader Account profile:</b> {user_name}</p>
                <p style="font-size: 16px;"><b>Backtest Period:</b> {final_start_date} to {final_end_date}</p>
                <p style="font-size: 16px;"><b>Total Trades Executed:</b> {total_trades}</p>
                <p style="font-size: 16px;"><b>Winning Trades:</b> {winning_trades}</p>
                <p style="font-size: 16px; color: #27ae60;"><b>Strategy Win Rate:</b> {win_rate:.2f}%</p>
                <h3 style="background-color: #f8f9fa; padding: 15px; text-align: center; border-radius: 5px; color: #2980b9;">
                    Cumulative Return: {total_return:.2f}%
                </h3>
            </div>
            """
        return f"<h3>Execution completed for {user_name}, but zero strategy signals were triggered.</h3>"

    except Exception as global_err:
        return f"<h3>Critical Application Crash: {global_err}</h3>"

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
