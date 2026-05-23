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
# ZERODHA API CONFIG
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
# GET ACCESS TOKEN
# ==========================================

def get_access_token():

    return os.getenv(
        "KITE_ACCESS_TOKEN",
        ""
    ).strip()

# ==========================================
# LOGIN ROUTE
# ==========================================

@app.route("/login")
def login():

    kite = KiteConnect(
        api_key=API_KEY
    )

    login_url = kite.login_url()

    return f"""

    <div style="
    font-family:sans-serif;
    padding:40px;
    ">

    <h1>
    Zerodha Login
    </h1>

    <a href="{login_url}">
    CLICK HERE TO LOGIN
    </a>

    </div>

    """

# ==========================================
# CALLBACK ROUTE
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
            Request Token Missing
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

        user_name = data.get(
            "user_name",
            "Trader"
        )

        return f"""

        <div style="
        font-family:sans-serif;
        padding:40px;
        max-width:900px;
        margin:auto;
        ">

        <h1 style="color:green;">
        ✅ LOGIN SUCCESSFUL
        </h1>

        <hr>

        <p>
        <b>User:</b>
        {user_name}
        </p>

        <p>
        <b>Copy this ACCESS TOKEN:</b>
        </p>

        <textarea
        rows="6"
        cols="100"
        style="
        width:100%;
        padding:10px;
        font-size:16px;
        "
        >
{access_token}
        </textarea>

        <hr>

        <h3>
        NEXT STEP
        </h3>

        <ol>
        <li>
        Copy this token
        </li>

        <li>
        Open Render
        </li>

        <li>
        Go to Environment Variables
        </li>

        <li>
        Replace:
        <b>KITE_ACCESS_TOKEN</b>
        </li>

        <li>
        Save Changes
        </li>

        <li>
        Deploy Latest Commit
        </li>
        </ol>

        <hr>

        <a href="/">
        Go To Backtest App
        </a>

        </div>

        """

    except Exception as e:

        return f"""

        <h1 style='color:red;'>
        LOGIN ERROR
        </h1>

        <pre>
        {str(e)}
        </pre>

        """

# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    try:

        # ==========================================
        # CHECK ACCESS TOKEN
        # ==========================================

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
            "15:00",
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
        # VARIABLES
        # ==========================================

        position = None

        entry_price = 0

        entry_time = None

        highest_price = 0

        trail_points = 150

        trades = []

        # ==========================================
        # MAIN LOOP
        # ==========================================

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]

            curr = df.iloc[i]

            # ==========================================
            # NO TRADE AFTER 14:45
            # ==========================================

            current_time = curr[
                "date"
            ].time()

            cutoff_time = datetime.strptime(
                "14:45",
                "%H:%M"
            ).time()

            allow_new_trade = (
                current_time
                < cutoff_time
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

                sl_hit = (
                    curr["close"]
                    < trailing_stop
                )

                crossover_exit = sell_signal

                if (
                    sl_hit
                    or
                    crossover_exit
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

                    option_entry = round(
                        entry_price * 0.0025,
                        2
                    )

                    option_exit = (
                        option_entry
                        + (pnl * 0.6)
                    )

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
                        ),

                        "exit_reason":
                        "SL HIT"
                        if sl_hit
                        else
                        "EMA EXIT"
                    })

                    # ==========================================
                    # REVERSE ONLY BEFORE 14:45
                    # ==========================================

                    if (
                        sl_hit
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

                highest_price = min(
                    highest_price,
                    curr["close"]
                )

                trailing_stop = (
                    highest_price
                    + trail_points
                )

                sl_hit = (
                    curr["close"]
                    > trailing_stop
                )

                crossover_exit = buy_signal

                if (
                    sl_hit
                    or
                    crossover_exit
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
                        ),

                        "exit_reason":
                        "SL HIT"
                        if sl_hit
                        else
                        "EMA EXIT"
                    })

                    # ==========================================
                    # REVERSE ONLY BEFORE 14:45
                    # ==========================================

                    if (
                        sl_hit
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
        # REPORT
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
        <b>User:</b> {user_name}
        </p>

        <p>
        <b>Total Trades:</b> {total_trades}
        </p>

        <p>
        <b>Winning Trades:</b> {wins}
        </p>

        <p>
        <b>Losing Trades:</b> {losses}
        </p>

        <p>
        <b>Win Rate:</b> {win_rate:.2f}%
        </p>

        <p>
        <b>Total Option PnL:</b>
        ₹ {round(total_pnl, 2)}
        </p>

        <hr>

        <a href="/download">
        📥 Download Excel Report
        </a>

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
