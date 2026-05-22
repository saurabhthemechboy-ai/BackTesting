import os
from datetime import datetime, timedelta

from flask import Flask
import pandas as pd
from kiteconnect import KiteConnect

app = Flask(__name__)

# ==========================================
# ENV VARIABLES
# ==========================================

API_KEY = os.getenv(
    "KITE_API_KEY",
    ""
).strip()

ACCESS_TOKEN = os.getenv(
    "KITE_ACCESS_TOKEN",
    ""
).strip()


@app.route("/")
def home():

    try:

        # ==========================================
        # CONNECT ZERODHA
        # ==========================================

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

        # ==========================================
        # FETCH 30 DAYS DATA
        # ==========================================

        to_date = datetime.now()

        from_date = (
            to_date
            - timedelta(days=30)
        )

        data = kite.historical_data(
            instrument_token=265,   # SENSEX
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

        # ==========================================
        # DATAFRAME
        # ==========================================

        df = pd.DataFrame(data)

        df["date"] = pd.to_datetime(
            df["date"]
        )

        # ==========================================
        # EMA CALCULATION
        # ==========================================

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

        # ==========================================
        # BACKTEST ENGINE
        # ==========================================

        position = None

        entry_price = 0

        trades = []

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            # BUY SIGNAL

            buy_signal = (

                curr["EMA9"]
                > curr["EMA21"]

                and

                prev["EMA9"]
                <= prev["EMA21"]
            )

            # SELL SIGNAL

            sell_signal = (

                curr["EMA9"]
                < curr["EMA21"]

                and

                prev["EMA9"]
                >= prev["EMA21"]
            )

            # ==========================================
            # ENTRY
            # ==========================================

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

            # ==========================================
            # EXIT BUY
            # ==========================================

            elif position == "BUY":

                if sell_signal:

                    exit_price = curr[
                        "close"
                    ]

                    pnl = (
                        exit_price
                        - entry_price
                    )

                    trades.append({

                        "type": "BUY",

                        "entry": round(
                            entry_price,
                            2
                        ),

                        "exit": round(
                            exit_price,
                            2
                        ),

                        "pnl": round(
                            pnl,
                            2
                        )
                    })

                    position = "SELL"

                    entry_price = curr[
                        "close"
                    ]

            # ==========================================
            # EXIT SELL
            # ==========================================

            elif position == "SELL":

                if buy_signal:

                    exit_price = curr[
                        "close"
                    ]

                    pnl = (
                        entry_price
                        - exit_price
                    )

                    trades.append({

                        "type": "SELL",

                        "entry": round(
                            entry_price,
                            2
                        ),

                        "exit": round(
                            exit_price,
                            2
                        ),

                        "pnl": round(
                            pnl,
                            2
                        )
                    })

                    position = "BUY"

                    entry_price = curr[
                        "close"
                    ]

        # ==========================================
        # RESULTS
        # ==========================================

        total_trades = len(
            trades
        )

        wins = len([
            t for t in trades
            if t["pnl"] > 0
        ])

        losses = (
            total_trades
            - wins
        )

        total_pnl = sum([
            t["pnl"]
            for t in trades
        ])

        win_rate = 0

        if total_trades > 0:

            win_rate = (
                wins
                / total_trades
            ) * 100

        # ==========================================
        # HTML REPORT
        # ==========================================

        return f"""

        <div style="
        font-family:sans-serif;
        max-width:800px;
        margin:auto;
        padding:30px;
        background:white;
        border-radius:10px;
        box-shadow:0 0 10px #ddd;
        ">

        <h1>
        📊 SENSEX BACKTEST REPORT
        </h1>

        <hr>

        <p>
        <b>User:</b>
        {user_name}
        </p>

        <p>
        <b>Total Trades:</b>
        {total_trades}
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

        <hr>

        <h3>
        Recent Trades
        </h3>

        <pre>
        {trades[:10]}
        </pre>

        </div>

        """

    except Exception as e:

        return f"""

        <h1 style='color:red;'>
        ERROR
        </h1>

        <pre>
        {str(e)}
        </pre>

        """


if __name__ == "__main__":
    app.run()
