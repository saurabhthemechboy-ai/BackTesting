import os
from datetime import datetime, timedelta

from flask import Flask
import pandas as pd
from kiteconnect import KiteConnect

app = Flask(__name__)

# =========================
# ENV VARIABLES
# =========================

API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")


@app.route("/")
def home():

    try:

        # =========================
        # CONNECT ZERODHA
        # =========================

        kite = KiteConnect(api_key=API_KEY)

        kite.set_access_token(ACCESS_TOKEN)

        profile = kite.profile()

        user_name = profile.get(
            "user_name",
            "Trader"
        )

        # =========================
        # 7 DAYS DATA
        # =========================

        to_date = datetime.now()

        from_date = (
            to_date
            - timedelta(days=7)
        )

        data = kite.historical_data(
            instrument_token=256265,
            from_date=from_date,
            to_date=to_date,
            interval="5minute"
        )

        if not data:

            return """
            <h2>No historical data received</h2>
            """

        # =========================
        # DATAFRAME
        # =========================

        df = pd.DataFrame(data)

        df["date"] = pd.to_datetime(
            df["date"]
        )

        # =========================
        # EMA
        # =========================

        df["EMA9"] = df["close"].ewm(
            span=9,
            adjust=False
        ).mean()

        df["EMA21"] = df["close"].ewm(
            span=21,
            adjust=False
        ).mean()

        # =========================
        # VWAP
        # =========================

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

        # =========================
        # BACKTEST ENGINE
        # =========================

        position = None

        entry_price = 0

        total_pnl = 0

        wins = 0

        losses = 0

        trades = 0

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            buy = (

                prev["EMA9"]
                < prev["EMA21"]

                and

                curr["EMA9"]
                > curr["EMA21"]

                and

                curr["close"]
                > curr["VWAP"]
            )

            sell = (

                prev["EMA9"]
                > prev["EMA21"]

                and

                curr["EMA9"]
                < curr["EMA21"]

                and

                curr["close"]
                < curr["VWAP"]
            )

            # =========================
            # ENTRY
            # =========================

            if position is None:

                if buy:

                    position = "BUY"

                    entry_price = curr["close"]

                elif sell:

                    position = "SELL"

                    entry_price = curr["close"]

            # =========================
            # EXIT BUY
            # =========================

            elif position == "BUY":

                if sell:

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

                    entry_price = curr["close"]

            # =========================
            # EXIT SELL
            # =========================

            elif position == "SELL":

                if buy:

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

                    entry_price = curr["close"]

        # =========================
        # WIN RATE
        # =========================

        if trades > 0:

            win_rate = (
                wins
                / trades
            ) * 100

        else:

            win_rate = 0

        # =========================
        # HTML OUTPUT
        # =========================

        return f"""
        <div style="
        font-family:sans-serif;
        max-width:700px;
        margin:auto;
        padding:30px;
        border-radius:10px;
        box-shadow:0 0 10px #ddd;
        ">

        <h1>
        📊 BACKTEST REPORT
        </h1>

        <hr>

        <p>
        <b>User:</b>
        {user_name}
        </p>

        <p>
        <b>Total Candles:</b>
        {len(df)}
        </p>

        <p>
        <b>Total Trades:</b>
        {trades}
        </p>

        <p>
        <b>Wins:</b>
        {wins}
        </p>

        <p>
        <b>Losses:</b>
        {losses}
        </p>

        <p>
        <b>Win Rate:</b>
        {win_rate:.2f}%
        </p>

        <p>
        <b>Total PnL:</b>
        {round(total_pnl,2)}
        </p>

        </div>
        """

    except Exception as e:

        return f"""
        <h2 style='color:red'>
        ERROR
        </h2>

        <p>{str(e)}</p>
        """


if __name__ == "__main__":
    app.run()
        """
if __name__ == "__main__":
    app.run()
