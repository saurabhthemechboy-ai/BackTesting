import os
from flask import Flask
from flask import send_file

from kiteconnect import KiteConnect

import pandas as pd

# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)

# ==========================================
# GLOBAL CACHE
# ==========================================

OPTION_CACHE = None

# ==========================================
# API CONFIG
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
# BASIC SETTINGS
# ==========================================

LOT_SIZE = 20

ENTRY_CUTOFF = "15:00"

SQUAREOFF_TIME = "15:25"

TRAIL_POINTS = 20

TRAIL_ACTIVATION = 30

STOPLOSS_PERCENT = 0.15

BACKTEST_DAYS = 10

INTERVAL = "5minute"

# ==========================================
# IMPORT MODULES
# ==========================================

from premium_engine import *

from report_engine import *

from strategy import *

# ==========================================
# HOME ROUTE
# ==========================================

@app.route("/")
def dashboard():

    try:

        # ==========================================
        # CHECK TOKEN
        # ==========================================

        if ACCESS_TOKEN == "":

            return """

            <h2>
            KITE_ACCESS_TOKEN Missing
            </h2>

            <p>
            Add today's access token
            in Render Environment Variables.
            </p>

            """

        # ==========================================
        # CONNECT KITE
        # ==========================================

        kite = KiteConnect(
            api_key=API_KEY
        )

        kite.set_access_token(
            ACCESS_TOKEN
        )

        # ==========================================
        # VERIFY LOGIN
        # ==========================================

        profile = kite.profile()

        user_name = profile.get(
            "user_name",
            "Trader"
        )

        # ==========================================
        # RUN STRATEGY ENGINE
        # ==========================================

        trades_df = run_strategy_engine(

            kite=kite,

            lot_size=LOT_SIZE,

            entry_cutoff=ENTRY_CUTOFF,

            squareoff_time=SQUAREOFF_TIME,

            trail_points=TRAIL_POINTS,

            trail_activation=TRAIL_ACTIVATION,

            stoploss_percent=STOPLOSS_PERCENT,

            backtest_days=BACKTEST_DAYS,

            interval=INTERVAL

        )

        # ==========================================
        # EMPTY CHECK
        # ==========================================

        if trades_df.empty:

            return """

            <h2>
            No Trades Generated
            </h2>

            """

        # ==========================================
        # REMOVE TIMEZONE
        # ==========================================

        trades_df["entry_time"] = pd.to_datetime(
            trades_df["entry_time"]
        ).dt.tz_localize(None)

        trades_df["exit_time"] = pd.to_datetime(
            trades_df["exit_time"]
        ).dt.tz_localize(None)

        # ==========================================
        # STATS
        # ==========================================

        total_trades = len(
            trades_df
        )

        wins = len(

            trades_df[
                trades_df[
                    "profit_amount"
                ] > 0
            ]

        )

        losses = (
            total_trades
            - wins
        )

        total_profit = trades_df[
            "profit_amount"
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
        padding:30px;
        max-width:900px;
        margin:auto;
        ">

        <h1>
        📊 REAL OPTION PREMIUM REPORT
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
        <b>Total Profit:</b>
        ₹ {round(total_profit, 2)}
        </p>

        <hr>

        <a href="/download">
        📥 DOWNLOAD EXCEL REPORT
        </a>

        </div>

        """

    except Exception as e:

        return f"""

        <h2>
        ERROR:
        {str(e)}
        </h2>

        """

# ==========================================
# DOWNLOAD ROUTE
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
