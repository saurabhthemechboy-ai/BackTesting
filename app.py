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

API_SECRET = os.getenv(
    "KITE_API_SECRET",
    ""
).strip()

# ==========================================
# LOAD NFO INSTRUMENTS
# ==========================================

def load_instruments(kite):

    global OPTION_CACHE

    if OPTION_CACHE is None:

        print(
            "LOADING NFO INSTRUMENTS..."
        )

        instruments = kite.instruments(
            "NFO"
        )

        OPTION_CACHE = pd.DataFrame(
            instruments
        )

        print(
            "NFO LOADED:",
            len(OPTION_CACHE)
        )

    return OPTION_CACHE

# ==========================================
# GET ATM OPTION TOKEN
# ==========================================

def get_option_token(

    kite,
    strike,
    option_type

):

    try:

        instruments_df = load_instruments(
            kite
        )

        # ==========================================
        # FILTER SENSEX
        # ==========================================

        df = instruments_df[

            instruments_df[
                "name"
            ] == "SENSEX"

        ]

        # ==========================================
        # CE / PE
        # ==========================================

        df = df[

            df[
                "instrument_type"
            ] == option_type

        ]

        # ==========================================
        # STRIKE
        # ==========================================

        df = df[

            df[
                "strike"
            ].astype(float)

            ==

            float(strike)

        ]

        # ==========================================
        # SORT NEAREST EXPIRY
        # ==========================================

        df = df.sort_values(
            by="expiry"
        )

        if df.empty:

            return None

        row = df.iloc[0]

        print(
            "OPTION FOUND:",
            row["tradingsymbol"]
        )

        return int(
            row[
                "instrument_token"
            ]
        )

    except Exception as e:

        print(
            "OPTION ERROR:",
            str(e)
        )

        return None

# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def index():

    return """

    <div style="
    font-family:sans-serif;
    padding:40px;
    ">

    <h1>
    📊 SENSEX BACKTEST ENGINE
    </h1>

    <br>

    <a href="/login">
    🔑 LOGIN TO ZERODHA
    </a>

    </div>

    """

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

        if not request_token:

            return """

            <h2>
            Request token missing
            </h2>

            """

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

        # ==========================================
        # SAVE TOKEN
        # ==========================================

        app.config[
            "ACCESS_TOKEN"
        ] = access_token

        # ==========================================
        # AUTO REDIRECT
        # ==========================================

        return redirect(
            "/dashboard"
        )

    except Exception as e:

        return f"""

        <h2>
        CALLBACK ERROR:
        {str(e)}
        </h2>

        """

# ==========================================
# DASHBOARD
# ==========================================

@app.route("/dashboard")
def dashboard():

    try:

        # ==========================================
        # ACCESS TOKEN
        # ==========================================

        access_token = app.config.get(
            "ACCESS_TOKEN"
        )

        if not access_token:

            return """

            <h2>
            Session expired
            </h2>

            <a href="/login">
            LOGIN AGAIN
            </a>

            """

        # ==========================================
        # CONNECT KITE
        # ==========================================

        kite = KiteConnect(
            api_key=API_KEY
        )

        kite.set_access_token(
            access_token
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
        # FETCH SENSEX DATA
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

            return """

            <h2>
            No Historical Data
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
        # MARKET HOURS
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

        trail_points = 30

        hard_sl_percent = 0.20

        lot_size = 20

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

            )

            # ==========================================
            # ENTRY
            # ==========================================

            if (

                position is None

                and

                allow_new_trade

            ):

                # ==========================================
                # BUY ENTRY
                # ==========================================

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

                    # ==========================================
                    # REAL CE TOKEN
                    # ==========================================

                    ce_token = get_option_token(

                        kite,
                        current_strike,
                        "CE"

                    )

                    print(
                        "CE TOKEN:",
                        ce_token
                    )

                # ==========================================
                # SELL ENTRY
                # ==========================================

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
                    # REAL PE TOKEN
                    # ==========================================

                    pe_token = get_option_token(

                        kite,
                        current_strike,
                        "PE"

                    )

                    print(
                        "PE TOKEN:",
                        pe_token
                    )

            # ==========================================
            # BUY POSITION
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

                trailing_sl_hit = (

                    curr["close"]
                    < trailing_stop
                )

                hard_sl_price = (

                    entry_price
                    * (1 - hard_sl_percent)

                )

                hard_sl_hit = (

                    curr["close"]
                    < hard_sl_price
                )

                crossover_exit = sell_signal

                if (

                    force_squareoff

                    or

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

                    profit_amount = round(
                        pnl * lot_size,
                        2
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
                        round(
                            entry_price,
                            2
                        ),

                        "exit_spot":
                        round(
                            exit_price,
                            2
                        ),

                        "profit_amount":
                        profit_amount,

                        "exit_reason":

                        "DAY END EXIT"
                        if force_squareoff

                        else

                        "HARD SL"
                        if hard_sl_hit

                        else

                        "TRAIL SL"
                        if trailing_sl_hit

                        else

                        "EMA EXIT"
                    })

                    position = None

            # ==========================================
            # SELL POSITION
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

                trailing_sl_hit = (

                    curr["close"]
                    > trailing_stop
                )

                hard_sl_price = (

                    entry_price
                    * (1 + hard_sl_percent)

                )

                hard_sl_hit = (

                    curr["close"]
                    > hard_sl_price
                )

                crossover_exit = buy_signal

                if (

                    force_squareoff

                    or

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

                    profit_amount = round(
                        pnl * lot_size,
                        2
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
                        round(
                            entry_price,
                            2
                        ),

                        "exit_spot":
                        round(
                            exit_price,
                            2
                        ),

                        "profit_amount":
                        profit_amount,

                        "exit_reason":

                        "DAY END EXIT"
                        if force_squareoff

                        else

                        "HARD SL"
                        if hard_sl_hit

                        else

                        "TRAIL SL"
                        if trailing_sl_hit

                        else

                        "EMA EXIT"
                    })

                    position = None

        # ==========================================
        # RESULTS
        # ==========================================

        trades_df = pd.DataFrame(
            trades
        )

        if trades_df.empty:

            return """

            <h2>
            No Trades Generated
            </h2>

            """

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

        return f"""

        <div style="
        font-family:sans-serif;
        padding:30px;
        max-width:900px;
        margin:auto;
        ">

        <h1>
        📊 EMA BACKTEST REPORT
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

        <br><br>

        <a href="/login">
        🔑 LOGIN AGAIN
        </a>

        </div>

        """

    except Exception as e:

        return f"""

        <h2>
        ERROR :
        {str(e)}
        </h2>

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
# RUN
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
