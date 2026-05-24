import pandas as pd

from datetime import timedelta

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
        # FILTER SENSEX
        # ==========================================

        df = instruments_df[

            instruments_df[
                "name"
            ] == "SENSEX"

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
        # NEAREST EXPIRY
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
            "OPTION TOKEN ERROR:",
            str(e)
        )

        return None

# ==========================================
# GET REAL OPTION PREMIUM
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

        # ==========================================
        # MATCH EXACT CANDLE
        # ==========================================

        # ==========================================
        # FIND NEAREST CANDLE
        # ==========================================

        option_df["time_diff"] = (

            option_df["date"]
            - candle_time

        ).abs()

        match = option_df.sort_values(
            by="time_diff"
        ).iloc[0]
    
        premium_price = float(

            match["close"]

        )

        return premium_price

    except Exception as e:

        print(
            "OPTION PRICE ERROR:",
            str(e)
        )

        return None
