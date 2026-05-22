import os
from datetime import datetime, timedelta

from flask import Flask
import pandas as pd
from kiteconnect import KiteConnect

app = Flask(__name__)

API_KEY = os.getenv("KITE_API_KEY", "").strip()

ACCESS_TOKEN = os.getenv(
    "KITE_ACCESS_TOKEN",
    ""
).strip()


@app.route("/")
def home():

    try:

        kite = KiteConnect(
            api_key=API_KEY
        )

        kite.set_access_token(
            ACCESS_TOKEN
        )

        profile = kite.profile()

        user_name = profile.get(
            "user_name",
            "Trader"
        )

        # 30 DAYS DATA

        to_date = datetime.now()

        from_date = (
            to_date
            - timedelta(days=30)
        )

        data = kite.historical_data(
            instrument_token=265,
            from_date=from_date,
            to_date=to_date,
            interval="5minute"
        )

        if not data:

            return "No data received"

        # DATAFRAME

        df = pd.DataFrame(data)

        df["date"] = pd.to_datetime(
            df["date"]
        )

        # EMA

        df["EMA9"] = df[
            "close"
        ].ewm(
            span=9,
            adjust=False
        ).mean()

        df["EMA21"] = df[
            "close"
        ].ewm(
            span=21,
            adjust=False
        ).mean()

        df = df.dropna().reset_index(
            drop=True
        )

        # DEBUG SIGNALS

        signals = []

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            buy_signal = (

                curr["EMA9"]
                > curr["EMA21"]

                and

                prev["EMA9"]
                <= prev["EMA21"]
            )

            sell_signal = (

                curr["EMA9"]
                < curr["EMA21"]

                and

                prev["EMA9"]
                >= prev["EMA21"]
            )

            if buy_signal:

                signals.append(
                    f"""
BUY at {curr['close']}
Time: {curr['date']}
"""
                )

            if sell_signal:

                signals.append(
                    f"""
SELL at {curr['close']}
Time: {curr['date']}
"""
                )

        return f"""

        <h1>
        EMA CROSSOVER DEBUG
        </h1>

        <p>
        User:
        {user_name}
        </p>

        <p>
        Total Signals:
        {len(signals)}
        </p>

        <pre>
        {signals[:20]}
        </pre>

        """

    except Exception as e:

        return f"""

        <h1>
        ERROR
        </h1>

        <pre>
        {str(e)}
        </pre>

        """


if __name__ == "__main__":
    app.run()
