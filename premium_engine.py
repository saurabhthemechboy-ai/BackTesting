import pandas as pd

# ==========================================
# GLOBAL CACHES
# ==========================================

OPTION_CACHE = None

PRICE_CACHE = {}

# ==========================================
# LOAD INSTRUMENTS
# ==========================================

def load_instruments(kite):

    global OPTION_CACHE

    if OPTION_CACHE is None:

        print(
            "LOADING NFO INSTRUMENTS..."
        )

        OPTION_CACHE = pd.DataFrame(

            kite.instruments("NFO")

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
            ] == "BANKNIFTY"

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
            "TOKEN ERROR:",
            str(e)
        )

        return None

# ==========================================
# LOAD OPTION DAY DATA
# ==========================================

def load_option_day_data(

    kite,
    option_token,
    candle_time

):

    global PRICE_CACHE

    cache_key = f"{option_token}_{candle_time.date()}"

    if cache_key in PRICE_CACHE:

        return PRICE_CACHE[
            cache_key
        ]

    try:

        candle_time = pd.to_datetime(
            candle_time
        ).tz_localize(None)

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
            "DOWNLOADING OPTION DATA..."
        )

        candles = kite.historical_data(

            instrument_token=option_token,

            from_date=start_day.to_pydatetime(),

            to_date=end_day.to_pydatetime(),

            interval="5minute"

        )

        if not candles:

            return None

        option_df = pd.DataFrame(
            candles
        )

        option_df["date"] = pd.to_datetime(
            option_df["date"]
        ).dt.tz_localize(None)

        PRICE_CACHE[
            cache_key
        ] = option_df

        return option_df

    except Exception as e:

        print(
            "CACHE LOAD ERROR:",
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

        option_df = load_option_day_data(

            kite,
            option_token,
            candle_time

        )

        if option_df is None:

            return None

        candle_time = pd.to_datetime(
            candle_time
        ).tz_localize(None)

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

        return premium_price

    except Exception as e:

        print(
            "PRICE ERROR:",
            str(e)
        )

        return None
