import pandas as pd

from datetime import datetime
from datetime import timedelta

from premium_engine import *

# ==========================================
# STRATEGY ENGINE
# ==========================================

def run_strategy_engine(

    kite,

    lot_size,

    entry_cutoff,

    squareoff_time,

    trail_points,

    trail_activation,

    stoploss_percent,

    backtest_days,

    interval

):

    # ==========================================
    # FETCH SENSEX DATA
    # ==========================================

    to_date = datetime.now()

    from_date = (
        to_date
        - timedelta(days=backtest_days)
    )

    data = kite.historical_data(

        instrument_token=265,

        from_date=from_date,

        to_date=to_date,

        interval=interval

    )

    if not data:

        return pd.DataFrame()

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
        squareoff_time,
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

    entry_option = None

    entry_strike = None

    trades = []

    # ==========================================
    # MAIN LOOP
    # ==========================================

    for i in range(1, len(df)):

        curr = df.iloc[i]

        current_time = curr[
            "date"
        ].time()

        # ==========================================
        # TIME RULES
        # ==========================================

        allow_entry = (

            current_time
            < datetime.strptime(
                entry_cutoff,
                "%H:%M"
            ).time()

        )

        # ==========================================
        # SIMPLE SIGNALS
        # ==========================================

        buy_signal = (

            curr["EMA9"]
            > curr["EMA21"]

        )

        sell_signal = (

            curr["EMA9"]
            < curr["EMA21"]

        )

        # ==========================================
        # ENTRY
        # ==========================================

        if (

            position is None

            and

            allow_entry

        ):

            strike = int(

                round(
                    curr["close"] / 100
                ) * 100

            )

            # ==========================================
            # BUY CE
            # ==========================================

            if buy_signal:

                option_token = get_option_token(

                    kite,
                    strike,
                    "CE"

                )

                premium = None

                if option_token is not None:

                    premium = get_option_price(

                        kite,
                        option_token,
                        curr["date"]

                    )

                if premium is None:

                    premium = (

                        curr["close"] * 0.01

                    )

                position = "BUY_CE"

                entry_price = premium

                entry_time = curr[
                    "date"
                ]

                entry_option = option_token

                entry_strike = strike

            # ==========================================
            # BUY PE
            # ==========================================

            elif sell_signal:

                option_token = get_option_token(

                    kite,
                    strike,
                    "PE"

                )

                premium = None

                if option_token is not None:

                    premium = get_option_price(

                        kite,
                        option_token,
                        curr["date"]

                    )

                if premium is None:

                    premium = (

                        curr["close"] * 0.01

                    )

                position = "BUY_PE"

                entry_price = premium

                entry_time = curr[
                    "date"
                ]

                entry_option = option_token

                entry_strike = strike

        # ==========================================
        # FORCE EXIT NEXT CANDLE
        # ==========================================

        elif position is not None:

            current_premium = None

            if entry_option is not None:

                current_premium = get_option_price(

                    kite,
                    entry_option,
                    curr["date"]

                )

            if current_premium is None:

                current_premium = (

                    curr["close"] * 0.01

                )

            # ==========================================
            # QUICK EXIT
            # ==========================================

            exit_price = current_premium

            pnl_points = (

                exit_price
                - entry_price

            )

            profit_amount = round(

                pnl_points
                * lot_size,

                2

            )

            trades.append({

                "trade_type":
                position,

                "strike":
                entry_strike,

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
                    pnl_points,
                    2
                ),

                "profit_amount":
                profit_amount,

                "exit_reason":
                "TEST EXIT"

            })

            # ==========================================
            # RESET POSITION
            # ==========================================

            position = None

    # ==========================================
    # FINAL DATAFRAME
    # ==========================================

    trades_df = pd.DataFrame(
        trades
    )

    return trades_df
