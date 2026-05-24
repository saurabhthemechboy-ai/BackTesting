import os
from datetime import datetime, timedelta

from flask import Flask
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

ACCESS_TOKEN = os.getenv(
    "KITE_ACCESS_TOKEN",
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
# GET OPTION TOKEN
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

        df = instruments_df[

            instruments_df[
                "name"
            ] == "SENSEX"

        ]

        df = df[

            df[
                "instrument_type"
            ] == option_type

        ]

        df = df[

            df[
                "strike"
            ].astype(float)

            ==

            float(strike)

        ]

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
# GET OPTION PREMIUM PRICE
# ==========================================

def get_option_price(

    kite,
    option_token,
    candle_time

):

    try:

        from_dt = candle_time - timedelta(
            minutes=5
        )

        to_dt = candle_time + timedelta(
            minutes=5
        )

        candles = kite.historical_data(

            instrument_token=option_token,

            from_date=from_dt,

            to_date=to_dt,

            interval="5minute"

        )

        if not candles:

            return None

        option_df = pd.DataFrame(
            candles
        )

        option_df["date"] = pd.to_datetime(
            option_df["date"]
        )

        match = option_df[

            option_df["date"]
            == candle_time

        ]

        if match.empty:

            return None

        premium_price = float(

            match.iloc[0]["close"]

        )

        return premium_price

    except Exception as e:

        print(
            "OPTION PRICE ERROR:",
            str(e)
        )

        return None

# ==========================================
# HOME
# ==========================================

@app.route("/")
def dashboard():

    try:

        if ACCESS_TOKEN == "":

            return """

            <h2>
            KITE_ACCESS_TOKEN Missing
            </h2>

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
            - timedelta(days=10)
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

        current_strike = None

        current_option = None

        trades = []

        highest_price = 0

        trail_points = 20

        trail_activation = 30

        lot_size = 20

        # ==========================================
        # LOOP
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

            allow_entry = (

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

            force_exit = (

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

                allow_entry

            ):

                current_strike = round(
                    curr["close"] / 100
                ) * 100

                # ==========================================
                # BUY CE
                # ==========================================

                if buy_signal:

                    option_token = get_option_token(

                        kite,
                        current_strike,
                        "CE"

                    )

                    if option_token is None:
                        continue

                    premium = get_option_price(

                        kite,
                        option_token,
                        curr["date"]

                    )

                    if premium is None:
                        continue

                    position = "BUY_CE"

                    current_option = option_token

                    entry_price = premium

                    entry_time = curr[
                        "date"
                    ]

                    highest_price = premium

                # ==========================================
                # BUY PE
                # ==========================================

                elif sell_signal:

                    option_token = get_option_token(

                        kite,
                        current_strike,
                        "PE"

                    )

                    if option_token is None:
                        continue

                    premium = get_option_price(

                        kite,
                        option_token,
                        curr["date"]

                    )

                    if premium is None:
                        continue

                    position = "BUY_PE"

                    current_option = option_token

                    entry_price = premium

                    entry_time = curr[
                        "date"
                    ]

                    highest_price = premium

            # ==========================================
            # ACTIVE POSITION
            # ==========================================

            elif position is not None:

                current_premium = get_option_price(

                    kite,
                    current_option,
                    curr["date"]

                )

                if current_premium is None:
                    continue

                # ==========================================
                # TRACK HIGH
                # ==========================================

                highest_price = max(
                    highest_price,
                    current_premium
                )

                # ==========================================
                # TRAILING ACTIVATION
                # ==========================================

                trail_active = (

                    highest_price
                    >= entry_price + trail_activation

                )

                if trail_active:

                    trailing_sl = (
                        highest_price
                        - trail_points
                    )

                    trailing_hit = (

                        current_premium
                        <= trailing_sl

                    )

                else:

                    trailing_hit = False

                # ==========================================
                # 15% SL
                # ==========================================

                sl_price = (
                    entry_price * 0.85
                )

                hard_sl_hit = (

                    current_premium
                    <= sl_price

                )

                # ==========================================
                # EXIT
                # ==========================================

                if (

                    force_exit

                    or

                    trailing_hit

                    or

                    hard_sl_hit

                ):

                    exit_price = current_premium

                    pnl = (
                        exit_price
                        - entry_price
                    )

                    profit_amount = round(
                        pnl * lot_size,
                        2
                    )

                    trades.append({

                        "trade":
                        position,

                        "strike":
                        current_strike,

                        "entry_time":
                        entry_time,

                        "exit_time":
                        curr["date"],

                        "entry_premium":
                        round(
                            entry_price,
                            2
                        ),

                        "exit_premium":
                        round(
                            exit_price,
                            2
                        ),

                        "points":
                        round(
                            pnl,
                            2
                        ),

                        "profit_amount":
                        profit_amount,

                        "exit_reason":

                        "DAY END"
                        if force_exit

                        else

                        "TRAIL SL"
                        if trailing_hit

                        else

                        "15% SL"
                    })

                    # ==========================================
                    # REVERSE ENTRY
                    # ==========================================

                    if hard_sl_hit and allow_entry:

                        reverse_type = (

                            "PE"
                            if position == "BUY_CE"
                            else "CE"

                        )

                        reverse_token = get_option_token(

                            kite,
                            current_strike,
                            reverse_type

                        )

                        reverse_price = get_option_price(

                            kite,
                            reverse_token,
                            curr["date"]

                        )

                        if reverse_price is not None:

                            position = (

                                "BUY_PE"
                                if reverse_type == "PE"
                                else "BUY_CE"

                            )

                            current_option = reverse_token

                            entry_price = reverse_price

                            entry_time = curr[
                                "date"
                            ]

                            highest_price = reverse_price

                        else:

                            position = None

                    else:

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

        total_profit = trades_df[
            "profit_amount"
        ].sum()

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

        win_rate = (
            wins / total_trades
        ) * 100

        # ==========================================
        # EXPORT
        # ==========================================

        excel_file = (
            "backtest_results.xlsx"
        )

        trades_df.to_excel(
            excel_file,
            index=False
        )

        # ==========================================
        # REPORT
        # ==========================================

        return f"""

        <div style="
        font-family:sans-serif;
        padding:30px;
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
