import pandas as pd

# ==========================================
# GLOBAL CACHE
# ==========================================

OPTION_CACHE = None

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

        # ==========================================
        # FILTER BANKNIFTY OPTIONS
        # ==========================================

        df = instruments_df[

            instruments_df[
                "name"
            ] == "BANKNIFTY"

        ]

        # ==========================================
        # OPTION TYPE
        # ==========================================

        df = df[

            df[
                "instrument_type"
            ] == option_type

        ]

        # ==========================================
        # STRIKE MATCH
        # ==========================================

        df = df[

            df[
                "strike"
            ].astype(float)

            ==

            float(strike)

        ]

        # ==========================================
        # NEAREST EXPIRY
        # ==========================================

        df = df.sort_values(
            by="expiry"
        )

        if df.empty:

            print(
                "NO OPTION FOUND"
            )

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
            "OPTION TOKEN ERROR:",
            str(e)
        )

        return None

# ==========================================
# GET OPTION PREMIUM
# ==========================================

def get_option_price(

    kite,
    option_token,
    candle_time

):

    try:

        # ==========================================
        # REMOVE TIMEZONE
        # ==========================================

        candle_time = pd.to_datetime(
            candle_time
        ).tz_localize(None)

        # ==========================================
        # BUILD CLEAN MARKET TIMES
        # ==========================================

        start_day = pd.Timestamp(

            year=candle_time.year,
            month=candle_time.month,
            day=candle_time.day,
            hour=9,
            minute=15

        )

        end_day = pd.Timestamp(

            year=candle_time.year,
            month=candle_time.month,
            day=candle_time.day,
            hour=15,
            minute=30

        )

        print(
            "FETCHING OPTION DATA"
        )

        candles = kite.historical_data(

            instrument_token=option_token,

            from_date=start_day.to_pydatetime(),

            to_date=end_day.to_pydatetime(),

            interval="5minute"

        )

        if not candles:

            print(
                "NO OPTION CANDLES"
            )

            return None

        option_df = pd.DataFrame(
            candles
        )

        option_df["date"] = pd.to_datetime(
            option_df["date"]
        ).dt.tz_localize(None)

        # ==========================================
        # FIND NEAREST CANDLE
        # ==========================================

        option_df["time_diff"] = (

            option_df["date"]
            - candle_time

        ).abs()

        nearest = option_df.sort_values(

            by="time_diff"

        ).iloc[0]

        premium_price = float(
            nearest["close"]
        )

        print(
            "PREMIUM PRICE:",
            premium_price
        )

        return premium_price

    except Exception as e:

        print(
            "OPTION PRICE ERROR:",
            str(e)
        )

        return None
