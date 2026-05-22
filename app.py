import os
from datetime import datetime, timedelta

from flask import Flask
import pandas as pd
from kiteconnect import KiteConnect

app = Flask(__name__)

API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")

@app.route("/")
def home():

    try:

        kite = KiteConnect(api_key=API_KEY)

        kite.set_access_token(ACCESS_TOKEN)

        # TEST LOGIN
        profile = kite.profile()

        # ONLY 7 DAYS DATA
        to_date = datetime.now()

        from_date = to_date - timedelta(days=7)

        data = kite.historical_data(
            instrument_token=256265,
            from_date=from_date,
            to_date=to_date,
            interval="5minute"
        )

        if not data:

            return "No data received"

        df = pd.DataFrame(data)

        # EMA
        df["EMA9"] = df["close"].ewm(
            span=9,
            adjust=False
        ).mean()

        df["EMA21"] = df["close"].ewm(
            span=21,
            adjust=False
        ).mean()

        # SIGNALS
        trades = 0

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            buy = (
                prev["EMA9"] < prev["EMA21"]
                and
                curr["EMA9"] > curr["EMA21"]
            )

            sell = (
                prev["EMA9"] > prev["EMA21"]
                and
                curr["EMA9"] < curr["EMA21"]
            )

            if buy or sell:
                trades += 1

        return f"""
        <h1>BACKTEST WORKING</h1>

        <p>User: {profile['user_name']}</p>

        <p>Total Candles: {len(df)}</p>

        <p>Total Signals: {trades}</p>
        """

    except Exception as e:

        return f"""
        <h2>ERROR</h2>

        <p>{str(e)}</p>
        """

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 8080)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
