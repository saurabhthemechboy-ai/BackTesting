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
        # BANKNIFTY FILTER
        # ==========================================

        df = instruments_df[

            instruments_df[
                "name"
            ] == "BANKNIFTY"

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
