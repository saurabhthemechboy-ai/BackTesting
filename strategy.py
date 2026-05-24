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

        instrument_token=260105,

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

    highest_price = 0

    trades = []

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
        # TIME RULES
        # ==========================================

        allow_entry = (

            current_time
            < datetime.strptime(
                entry_cutoff,
                "%H:%M"
            ).time()

        )

        force_exit = (

            current_time
            >= datetime.strptime(
                squareoff_time,
                "%H:%M"
            ).time()

        )

        # ==========================================
        # SIGNALS
        # ==========================================

        buy_signal = (

            curr["EMA9"]
            > curr["EMA21"]

            and

            prev["EMA9"]
            <= prev["EMA21"]

        )

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

            strike = round(
                curr["close"] / 100
            ) * 100

            # ==========================================
            # BUY CE
            # ==========================================

            if buy_signal:

                option_token = get_option_token(

                    kite,
                    strike,
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
                    premium = 100
                    continue

                position = "BUY_CE"

                entry_price = premium

                entry_time = curr[
                    "date"
                ]

                entry_option = option_token

                entry_strike = strike

                highest_price = premium

            # ==========================================
            # BUY PE
            # ==========================================

            elif sell_signal:

                option_token = get_option_token(

                    kite,
                    strike,
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
                    premium = 100
                    continue

                position = "BUY_PE"

                entry_price = premium

                entry_time = curr[
                    "date"
                ]

                entry_option = option_token

                entry_strike = strike

                highest_price = premium

        # ==========================================
        # ACTIVE POSITION
        # ==========================================

        elif position is not None:

            current_premium = get_option_price(

                kite,
                entry_option,
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
            # TRAILING ACTIVE
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
            # FIXED SL
            # ==========================================

            sl_price = (

                entry_price
                * (1 - stoploss_percent)

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

                if (

                    hard_sl_hit

                    and

                    allow_entry

                ):

                    reverse_type = (

                        "PE"
                        if position == "BUY_CE"
                        else "CE"

                    )

                    reverse_token = get_option_token(

                        kite,
                        entry_strike,
                        reverse_type

                    )

                    if reverse_token is not None:

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

                            entry_price = reverse_price

                            entry_time = curr[
                                "date"
                            ]

                            entry_option = reverse_token

                            highest_price = reverse_price

                        else:

                            position = None

                    else:

                        position = None

                else:

                    position = None

    # ==========================================
    # FINAL DATAFRAME
    # ==========================================

    trades_df = pd.DataFrame(
        trades
    )

    return trades_df
