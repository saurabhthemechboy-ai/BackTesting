import os
from datetime import datetime, timedelta

from flask import Flask
from flask import send_file

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
        # CONNECT TO ZERODHA
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
        # FETCH HISTORICAL DATA
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

        entry_time = None

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

                    entry_time = curr[
                        "date"
                    ]

                elif sell_signal:

                    position = "SELL"

                    entry_price = curr[
                        "close"
                    ]

                    entry_time = curr[
                        "date"
                    ]

            # ==========================================
            # EXIT BUY
            # ==========================================

            elif position == "BUY":

                if sell_signal:

                    exit_price = curr[
                        "close"
                    ]

                    exit_time = curr[
                        "date"
                    ]

                    pnl = (
                        exit_price
                        - entry_price
                    )

                    trades.append({

                        "trade_type":
                        "BUY",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        exit_time,

                        "entry_price":
                        round(
                            entry_price,
                            2
                        ),

                        "exit_price":
                        round(
                            exit_price,
                            2
                        ),

                        "pnl":
                        round(
                            pnl,
                            2
                        )
                    })

                    position = "SELL"

                    entry_price = curr[
                        "close"
                    ]

                    entry_time = curr[
                        "date"
                    ]

            # ==========================================
            # EXIT SELL
            # ==========================================

            elif position == "SELL":

                if buy_signal:

                    exit_price = curr[
                        "close"
                    ]

                    exit_time = curr[
                        "date"
                    ]

                    pnl = (
                        entry_price
                        - exit_price
                    )

                    trades.append({

                        "trade_type":
                        "SELL",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        exit_time,

                        "entry_price":
                        round(
                            entry_price,
                            2
                        ),

                        "exit_price":
                        round(
                            exit_price,
                            2
                        ),

                        "pnl":
                        round(
                            pnl,
                            2
                        )
                    })

                    position = "BUY"

                    entry_price = curr[
                        "close"
                    ]

                    entry_time = curr[
                        "date"
                    ]

        # ==========================================
        # CREATE DATAFRAME
        # ==========================================

        trades_df = pd.DataFrame(
            trades
        )

        if trades_df.empty:

            return """
            <h2>
            No trades generated
            </h2>
            """

        # ==========================================
        # RESULTS
        # ==========================================

        trades_df["result"] = trades_df[
            "pnl"
        ].apply(
            lambda x:
            "WIN"
            if x > 0
            else "LOSS"
        )

        trades_df["cumulative_pnl"] = trades_df[
            "pnl"
        ].cumsum()

        total_trades = len(
            trades_df
        )

        wins = len(
            trades_df[
                trades_df["pnl"] > 0
            ]
        )

        losses = (
            total_trades
            - wins
        )

        total_pnl = trades_df[
            "pnl"
        ].sum()

        win_rate = (
            wins / total_trades
        ) * 100

        # ==========================================
        # EXPORT EXCEL
        # ==========================================

        excel_file = (
            "backtest_results.xlsx"
        )

        trades_df.to_excel(
            excel_file,
            index=False
        )

        # ==========================================
        # HTML REPORT
        # ==========================================

        return f"""

        <div style="
        font-family:sans-serif;
        max-width:900px;
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

        <a href="/download">
        📥 Download Excel Report
        </a>

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


@app.route("/download")
def download_file():

    return send_file(
        "backtest_results.xlsx",
        as_attachment=True
    )


if __name__ == "__main__":
    app.run()
