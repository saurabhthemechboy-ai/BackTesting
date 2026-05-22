import os
from datetime import datetime, timedelta

from flask import Flask
from flask import send_file

import pandas as pd

from kiteconnect import KiteConnect

app = Flask(__name__)

# ==========================================
# ZERODHA CREDENTIALS
# ==========================================

API_KEY = os.getenv(
    "KITE_API_KEY",
    ""
).strip()

ACCESS_TOKEN = os.getenv(
    "KITE_ACCESS_TOKEN",
    ""
).strip()

# ==========================================
# HOME
# ==========================================

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
        # FETCH HISTORICAL DATA
        # ==========================================

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

            return "<h2>No Historical Data Received</h2>"

        # ==========================================
        # DATAFRAME
        # ==========================================

        df = pd.DataFrame(data)

        df["date"] = pd.to_datetime(
            df["date"]
        )

        # ==========================================
        # MARKET TIME FILTER
        # ==========================================

        df["time"] = df["date"].dt.time

        market_start = datetime.strptime(
            "09:20",
            "%H:%M"
        ).time()

        market_end = datetime.strptime(
            "15:00",
            "%H:%M"
        ).time()

        df = df[
            (
                df["time"] >= market_start
            )
            &
            (
                df["time"] <= market_end
            )
        ]

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

        highest_price = 0

        trail_points = 150

        trades = []

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            # ==========================================
            # BUY SIGNAL
            # ==========================================

            buy_signal = (

                curr["EMA9"]
                > curr["EMA21"]

                and

                prev["EMA9"]
                <= prev["EMA21"]

                and

                (
                    curr["high"]
                    - curr["low"]
                ) > 20
            )

            # ==========================================
            # SELL SIGNAL
            # ==========================================

            sell_signal = (

                curr["EMA9"]
                < curr["EMA21"]

                and

                prev["EMA9"]
                >= prev["EMA21"]

                and

                (
                    curr["high"]
                    - curr["low"]
                ) > 20
            )

            # ==========================================
            # ENTRY CONDITIONS
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

                    highest_price = curr[
                        "close"
                    ]

                elif sell_signal:

                    position = "SELL"

                    entry_price = curr[
                        "close"
                    ]

                    entry_time = curr[
                        "date"
                    ]

                    highest_price = curr[
                        "close"
                    ]

            # ==========================================
            # BUY TRADE MANAGEMENT
            # ==========================================

            elif position == "BUY":

                highest_price = max(
                    highest_price,
                    curr["close"]
                )

                trailing_stop = (
                    highest_price
                    - trail_points
                )

                if (
                    sell_signal
                    or
                    curr["close"]
                    < trailing_stop
                ):

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

                    strike = round(
                        entry_price / 100
                    ) * 100

                    # ==========================================
                    # OPTION PREMIUM SIMULATION
                    # ==========================================

                    option_entry = round(
                        entry_price * 0.0025,
                        2
                    )

                    option_exit = (
                        option_entry
                        + (pnl * 0.6)
                    )

                    # ==========================================
                    # FIXED STOP LOSS
                    # ==========================================

                    max_loss = (
                        option_entry * 0.10
                    )

                    minimum_exit = (
                        option_entry - max_loss
                    )

                    if option_exit < minimum_exit:

                        option_exit = minimum_exit

                    lot_size = 20

                    real_pnl = (
                        option_exit
                        - option_entry
                    ) * lot_size

                    trades.append({

                        "trade_type":
                        "BUY CE",

                        "strike":
                        f"{strike} CE",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        exit_time,

                        "spot_entry":
                        round(
                            entry_price,
                            2
                        ),

                        "spot_exit":
                        round(
                            exit_price,
                            2
                        ),

                        "option_buy":
                        round(
                            option_entry,
                            2
                        ),

                        "option_sell":
                        round(
                            option_exit,
                            2
                        ),

                        "points":
                        round(
                            pnl,
                            2
                        ),

                        "real_pnl":
                        round(
                            real_pnl,
                            2
                        )
                    })

                    # REVERSE POSITION

                    position = "SELL"

                    entry_price = curr[
                        "close"
                    ]

                    entry_time = curr[
                        "date"
                    ]

                    highest_price = curr[
                        "close"
                    ]

            # ==========================================
            # SELL TRADE MANAGEMENT
            # ==========================================

            elif position == "SELL":

                highest_price = min(
                    highest_price,
                    curr["close"]
                )

                trailing_stop = (
                    highest_price
                    + trail_points
                )

                if (
                    buy_signal
                    or
                    curr["close"]
                    > trailing_stop
                ):

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

                    strike = round(
                        entry_price / 100
                    ) * 100

                    option_entry = round(
                        entry_price * 0.0025,
                        2
                    )

                    option_exit = (
                        option_entry
                        + (pnl * 0.6)
                    )

                    # ==========================================
                    # FIXED STOP LOSS
                    # ==========================================

                    max_loss = (
                        option_entry * 0.10
                    )

                    minimum_exit = (
                        option_entry - max_loss
                    )

                    if option_exit < minimum_exit:

                        option_exit = minimum_exit

                    lot_size = 20

                    real_pnl = (
                        option_exit
                        - option_entry
                    ) * lot_size

                    trades.append({

                        "trade_type":
                        "BUY PE",

                        "strike":
                        f"{strike} PE",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        exit_time,

                        "spot_entry":
                        round(
                            entry_price,
                            2
                        ),

                        "spot_exit":
                        round(
                            exit_price,
                            2
                        ),

                        "option_buy":
                        round(
                            option_entry,
                            2
                        ),

                        "option_sell":
                        round(
                            option_exit,
                            2
                        ),

                        "points":
                        round(
                            pnl,
                            2
                        ),

                        "real_pnl":
                        round(
                            real_pnl,
                            2
                        )
                    })

                    # REVERSE POSITION

                    position = "BUY"

                    entry_price = curr[
                        "close"
                    ]

                    entry_time = curr[
                        "date"
                    ]

                    highest_price = curr[
                        "close"
                    ]

        # ==========================================
        # RESULTS DATAFRAME
        # ==========================================

        trades_df = pd.DataFrame(
            trades
        )

        if trades_df.empty:

            return "<h2>No Trades Generated</h2>"

        # ==========================================
        # REMOVE TIMEZONE FOR EXCEL
        # ==========================================

        trades_df["entry_time"] = pd.to_datetime(
            trades_df["entry_time"]
        ).dt.tz_localize(None)

        trades_df["exit_time"] = pd.to_datetime(
            trades_df["exit_time"]
        ).dt.tz_localize(None)

        # ==========================================
        # RESULT ANALYSIS
        # ==========================================

        trades_df["result"] = trades_df[
            "real_pnl"
        ].apply(
            lambda x:
            "WIN"
            if x > 0
            else "LOSS"
        )

        trades_df["cumulative_pnl"] = trades_df[
            "real_pnl"
        ].cumsum()

        total_trades = len(
            trades_df
        )

        wins = len(
            trades_df[
                trades_df["real_pnl"] > 0
            ]
        )

        losses = (
            total_trades
            - wins
        )

        total_pnl = trades_df[
            "real_pnl"
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
        max-width:1000px;
        margin:auto;
        padding:30px;
        background:white;
        border-radius:10px;
        box-shadow:0 0 10px #ddd;
        ">

        <h1>
        📊 SENSEX OPTION BACKTEST REPORT
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
        <b>Total Option PnL:</b>
        ₹ {round(total_pnl, 2)}
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


# ==========================================
# DOWNLOAD EXCEL
# ==========================================

@app.route("/download")
def download_file():

    return send_file(
        "backtest_results.xlsx",
        as_attachment=True
    )


# ==========================================
# RUN APP
# ==========================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
