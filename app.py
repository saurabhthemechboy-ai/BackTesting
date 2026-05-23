import os
from datetime import datetime, timedelta

from flask import Flask
from flask import request
from flask import redirect
from flask import send_file

import pandas as pd

from kiteconnect import KiteConnect

app = Flask(__name__)

# ==========================================
# API CONFIG
# ==========================================

API_KEY = os.getenv(
    "KITE_API_KEY",
    ""
).strip()

API_SECRET = os.getenv(
    "KITE_API_SECRET",
    ""
).strip()

# ==========================================
# ACCESS TOKEN
# ==========================================

def get_access_token():

    return os.getenv(
        "KITE_ACCESS_TOKEN",
        ""
    ).strip()

# ==========================================
# LOGIN
# ==========================================

@app.route("/login")
def login():

    kite = KiteConnect(
        api_key=API_KEY
    )

    return redirect(
        kite.login_url()
    )

# ==========================================
# CALLBACK
# ==========================================

@app.route("/callback")
def callback():

    try:

        request_token = request.args.get(
            "request_token"
        )

        kite = KiteConnect(
            api_key=API_KEY
        )

        data = kite.generate_session(
            request_token,
            api_secret=API_SECRET
        )

        access_token = data[
            "access_token"
        ]

        return f"""

        <h1>
        ACCESS TOKEN
        </h1>

        <textarea
        rows="8"
        cols="100"
        >
{access_token}
        </textarea>

        """

    except Exception as e:

        return f"""
        ERROR : {str(e)}
        """

# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    try:

        if get_access_token() == "":

            return redirect(
                "/login"
            )

        # ==========================================
        # CONNECT ZERODHA
        # ==========================================

        kite = KiteConnect(
            api_key=API_KEY
        )

        kite.set_access_token(
            get_access_token()
        )

        profile = kite.profile()

        user_name = profile.get(
            "user_name",
            "Trader"
        )

        # ==========================================
        # FETCH DATA
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

            return "No Historical Data"

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

        df["time"] = df[
            "date"
        ].dt.time

        market_start = datetime.strptime(
            "09:20",
            "%H:%M"
        ).time()

        market_end = datetime.strptime(
            "15:25",
            "%H:%M"
        ).time()

        df = df[
            (
                df["time"]
                >= market_start
            )
            &
            (
                df["time"]
                <= market_end
            )
        ]

        # ==========================================
        # EMA
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

        # ==========================================
        # VWAP
        # ==========================================

        df["date_only"] = df[
            "date"
        ].dt.date

        df["vol_price"] = (
            df["close"]
            * df["volume"]
        )

        df["cum_vol"] = df.groupby(
            "date_only"
        )["volume"].cumsum()

        df["cum_vol_price"] = df.groupby(
            "date_only"
        )["vol_price"].cumsum()

        df["VWAP"] = (
            df["cum_vol_price"]
            / df["cum_vol"]
        )

        df = df.dropna().reset_index(
            drop=True
        )

        # ==========================================
        # VARIABLES
        # ==========================================

        position = None

        entry_price = 0

        entry_time = None

        highest_price = 0

        current_strike = None

        trades = []

        trail_points = 80

        # ==========================================
        # MAIN LOOP
        # ==========================================

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            current_time = curr[
                "date"
            ].time()

            # ==========================================
            # ENTRY CUTOFF
            # ==========================================

            entry_cutoff = datetime.strptime(
                "15:00",
                "%H:%M"
            ).time()

            allow_new_trade = (
                current_time
                < entry_cutoff
            )

            # ==========================================
            # FORCE EXIT
            # ==========================================

            squareoff_time = datetime.strptime(
                "15:25",
                "%H:%M"
            ).time()

            force_squareoff = (
                current_time
                >= squareoff_time
            )

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

                curr["close"]
                > curr["VWAP"]
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

                curr["close"]
                < curr["VWAP"]
            )

            # ==========================================
            # ENTRY
            # ==========================================

            if (

                position is None

                and

                allow_new_trade
            ):

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

                    current_strike = round(
                        curr["close"] / 100
                    ) * 100

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

                    current_strike = round(
                        curr["close"] / 100
                    ) * 100

            # ==========================================
            # BUY POSITION
            # ==========================================

            elif position == "BUY":

                # ==========================================
                # DAY END EXIT
                # ==========================================

                if force_squareoff:

                    exit_price = curr[
                        "close"
                    ]

                    pnl = (
                        exit_price
                        - entry_price
                    )

                    trades.append({

                        "trade_type":
                        "BUY CE",

                        "strike":
                        f"{current_strike} CE",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        curr["date"],

                        "entry_spot":
                        round(entry_price, 2),

                        "exit_spot":
                        round(exit_price, 2),

                        "points":
                        round(pnl, 2),

                        "exit_reason":
                        "DAY END EXIT"
                    })

                    position = None

                    continue

                highest_price = max(
                    highest_price,
                    curr["close"]
                )

                trailing_stop = (
                    highest_price
                    - trail_points
                )

                # ==========================================
                # TRAILING SL
                # ==========================================

                trailing_sl_hit = (

                    curr["close"]
                    < trailing_stop
                )

                # ==========================================
                # HARD SL
                # ==========================================

                hard_sl_hit = (

                    curr["close"]
                    < (
                        entry_price - 60
                    )
                )

                # ==========================================
                # EMA EXIT
                # ==========================================

                crossover_exit = sell_signal

                # ==========================================
                # EXIT CONDITIONS
                # ==========================================

                if (

                    trailing_sl_hit

                    or

                    hard_sl_hit

                    or

                    crossover_exit
                ):

                    exit_price = curr[
                        "close"
                    ]

                    pnl = (
                        exit_price
                        - entry_price
                    )

                    trades.append({

                        "trade_type":
                        "BUY CE",

                        "strike":
                        f"{current_strike} CE",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        curr["date"],

                        "entry_spot":
                        round(entry_price, 2),

                        "exit_spot":
                        round(exit_price, 2),

                        "points":
                        round(pnl, 2),

                        "exit_reason":

                        "HARD SL"
                        if hard_sl_hit

                        else

                        "TRAIL SL"
                        if trailing_sl_hit

                        else

                        "EMA EXIT"
                    })

                    # ==========================================
                    # REVERSE ONLY ON HARD SL
                    # ==========================================

                    if (

                        hard_sl_hit

                        and

                        allow_new_trade
                    ):

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

                    else:

                        position = None

            # ==========================================
            # SELL POSITION
            # ==========================================

            elif position == "SELL":

                # ==========================================
                # DAY END EXIT
                # ==========================================

                if force_squareoff:

                    exit_price = curr[
                        "close"
                    ]

                    pnl = (
                        entry_price
                        - exit_price
                    )

                    trades.append({

                        "trade_type":
                        "BUY PE",

                        "strike":
                        f"{current_strike} PE",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        curr["date"],

                        "entry_spot":
                        round(entry_price, 2),

                        "exit_spot":
                        round(exit_price, 2),

                        "points":
                        round(pnl, 2),

                        "exit_reason":
                        "DAY END EXIT"
                    })

                    position = None

                    continue

                highest_price = min(
                    highest_price,
                    curr["close"]
                )

                trailing_stop = (
                    highest_price
                    + trail_points
                )

                # ==========================================
                # TRAILING SL
                # ==========================================

                trailing_sl_hit = (

                    curr["close"]
                    > trailing_stop
                )

                # ==========================================
                # HARD SL
                # ==========================================

                hard_sl_hit = (

                    curr["close"]
                    > (
                        entry_price + 60
                    )
                )

                # ==========================================
                # EMA EXIT
                # ==========================================

                crossover_exit = buy_signal

                # ==========================================
                # EXIT CONDITIONS
                # ==========================================

                if (

                    trailing_sl_hit

                    or

                    hard_sl_hit

                    or

                    crossover_exit
                ):

                    exit_price = curr[
                        "close"
                    ]

                    pnl = (
                        entry_price
                        - exit_price
                    )

                    trades.append({

                        "trade_type":
                        "BUY PE",

                        "strike":
                        f"{current_strike} PE",

                        "entry_time":
                        entry_time,

                        "exit_time":
                        curr["date"],

                        "entry_spot":
                        round(entry_price, 2),

                        "exit_spot":
                        round(exit_price, 2),

                        "points":
                        round(pnl, 2),

                        "exit_reason":

                        "HARD SL"
                        if hard_sl_hit

                        else

                        "TRAIL SL"
                        if trailing_sl_hit

                        else

                        "EMA EXIT"
                    })

                    # ==========================================
                    # REVERSE ONLY ON HARD SL
                    # ==========================================

                    if (

                        hard_sl_hit

                        and

                        allow_new_trade
                    ):

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

                    else:

                        position = None

        # ==========================================
        # RESULTS
        # ==========================================

        trades_df = pd.DataFrame(
            trades
        )

        if trades_df.empty:

            return "No Trades Generated"

        trades_df["entry_time"] = pd.to_datetime(
            trades_df["entry_time"]
        ).dt.tz_localize(None)

        trades_df["exit_time"] = pd.to_datetime(
            trades_df["exit_time"]
        ).dt.tz_localize(None)

        total_trades = len(
            trades_df
        )

        wins = len(
            trades_df[
                trades_df["points"] > 0
            ]
        )

        losses = (
            total_trades
            - wins
        )

        total_points = trades_df[
            "points"
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

        return f"""

        <div style="
        font-family:sans-serif;
        padding:30px;
        max-width:900px;
        margin:auto;
        ">

        <h1>
        📊 EMA + VWAP BACKTEST
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
        <b>Total Points:</b>
        {round(total_points, 2)}
        </p>

        <hr>

        <a href="/download">
        📥 DOWNLOAD EXCEL REPORT
        </a>

        </div>

        """

    except Exception as e:

        return f"""
        ERROR : {str(e)}
        """

# ==========================================
# DOWNLOAD
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
