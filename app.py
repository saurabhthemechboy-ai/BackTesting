import os
from datetime import datetime, timedelta

from flask import Flask
import pandas as pd
from kiteconnect import KiteConnect

app = Flask(__name__)

# ======================================
# ENV VARIABLES
# ======================================

API_KEY = os.getenv("KITE_API_KEY", "").strip()

ACCESS_TOKEN = os.getenv(
    "KITE_ACCESS_TOKEN",
    ""
).strip()


@app.route("/")
def home():

    try:

        # ======================================
        # CHECK API DETAILS
        # ======================================

        if not API_KEY or not ACCESS_TOKEN:

            return """
            <h2 style='color:red;'>
            Missing KITE_API_KEY or KITE_ACCESS_TOKEN
            </h2>
            """

        # ======================================
        # CONNECT ZERODHA
        # ======================================

        kite = KiteConnect(api_key=API_KEY)

        kite.set_access_token(ACCESS_TOKEN)

        profile = kite.profile()

        user_name = profile.get(
            "user_name",
            "Trader"
        )

        # ======================================
        # FETCH 7 DAYS DATA
        # ======================================

        to_date = datetime.now()

        from_date = (
            to_date
            - timedelta(days=7)
        )

        data = kite.historical_data(
            instrument_token=256265,  # NIFTY
            from_date=from_date,
            to_date=to_date,
            interval="5minute"
        )

        if not data:

            return """
            <h2>
            No historical data received
            </h2>
            """

        # ======================================
        # DATAFRAME
        # ======================================

        df = pd.DataFrame(data)

        df["date"] = pd.to_datetime(
            df["date"]
        )

        # ======================================
        # MARKET TIME FILTER
        # ======================================

        df["time"] = df[
            "date"
        ].dt.time

        market_start = datetime.strptime(
            "09:20",
            "%H:%M"
        ).time()

        market_end = datetime.strptime(
            "14:30",
            "%H:%M"
        ).time()

        df = df[
            (df["time"] >= market_start)
            &
            (df["time"] <= market_end)
        ].copy()

        # ======================================
        # EMA
        # ======================================

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

        # ======================================
        # VWAP
        # ======================================

        df["date_only"] = (
            df["date"].dt.date
        )

        df["vol_price"] = (
            df["close"]
            * df["volume"]
        )

        df["cum_volume"] = df.groupby(
            "date_only"
        )["volume"].cumsum()

        df["cum_vol_price"] = df.groupby(
            "date_only"
        )["vol_price"].cumsum()

        df["VWAP"] = (
            df["cum_vol_price"]
            / df["cum_volume"]
        )

        # ======================================
        # DROP NAN
        # ======================================

        df = df.dropna().reset_index(
            drop=True
        )

        # ======================================
        # BACKTEST ENGINE
        # ======================================

        position = None

        entry_price = 0

        total_pnl = 0

        wins = 0

        losses = 0

        trades = 0

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            buy_signal = (

                prev["EMA9"]
                < prev["EMA21"]

                and

                curr["EMA9"]
                > curr["EMA21"]

                and

                curr["close"]
                > curr["VWAP"]
            )

            sell_signal = (

                prev["EMA9"]
                > prev["EMA21"]

                and

                curr["EMA9"]
                < curr["EMA21"]

                and

                curr["close"]
                < curr["VWAP"]
            )

            # ENTRY

            if position is None:

                if buy_signal:

                    position = "BUY"

                    entry_price = curr[
                        "close"
                    ]

                elif sell_signal:

                    position = "SELL"

                    entry_price = curr[
                        "close"
                    ]

            # EXIT BUY

            elif position == "BUY":

                if sell_signal:

                    pnl = (

                        curr["close"]

                        - entry_price
                    )

                    total_pnl += pnl

                    trades += 1

                    if pnl > 0:

                        wins += 1

                    else:

                        losses += 1

                    position = "SELL"

                    entry_price = curr[
                        "close"
                    ]

            # EXIT SELL

            elif position == "SELL":

                if buy_signal:

                    pnl = (

                        entry_price

                        - curr["close"]
                    )

                    total_pnl += pnl

                    trades += 1

                    if pnl > 0:

                        wins += 1

                    else:

                        losses += 1

                    position = "BUY"

                    entry_price = curr[
                        "close"
                    ]

        # ======================================
        # RESULTS
        # ======================================

        win_rate = 0

        if trades > 0:

            win_rate = (
                wins / trades
            ) * 100

        return f"""

        <div style="
        font-family:sans-serif;
        max-width:700px;
        margin:auto;
        padding:30px;
        border-radius:10px;
        box-shadow:0 0 10px #ddd;
        background:white;
        ">

        <h1>
        📊 NIFTY BACKTEST REPORT
        </h1>

        <hr>

        <p>
        <b>User:</b>
        {user_name}
        </p>

        <p>
        <b>Total Trades:</b>
        {trades}
        </p>

        <p>
        <b>Winning Trades:</b>
        {wins}
        </p>

        <p>
        <b>Losing Trades:</b>
        {losses}
        </p>

        <p>
        <b>Win Rate:</b>
        {win_rate:.2f}%
        </p>

        <p>
        <b>Total PnL:</b>
        {round(total_pnl, 2)}
        </p>

        </div>
        """

    except Exception as e:

        return f"""
        <h2 style='color:red;'>
        ERROR
        </h2>

        <p>{str(e)}</p>
        """


if __name__ == "__main__":
    app.run()
