import pandas as pd

# ==========================================
# CLEAN DATETIME
# ==========================================

def clean_trade_dataframe(

    trades_df

):

    if trades_df.empty:

        return trades_df

    # ==========================================
    # REMOVE TIMEZONE
    # ==========================================

    trades_df["entry_time"] = pd.to_datetime(

        trades_df["entry_time"]

    ).dt.tz_localize(None)

    trades_df["exit_time"] = pd.to_datetime(

        trades_df["exit_time"]

    ).dt.tz_localize(None)

    return trades_df

# ==========================================
# BUILD STATS
# ==========================================

def generate_statistics(

    trades_df

):

    if trades_df.empty:

        return {

            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_profit": 0

        }

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

    total_profit = round(

        trades_df[
            "profit_amount"
        ].sum(),

        2

    )

    win_rate = round(

        (
            wins / total_trades
        ) * 100,

        2

    )

    return {

        "total_trades":
        total_trades,

        "wins":
        wins,

        "losses":
        losses,

        "win_rate":
        win_rate,

        "total_profit":
        total_profit

    }

# ==========================================
# EXPORT EXCEL
# ==========================================

def export_excel(

    trades_df,

    file_name="backtest_results.xlsx"

):

    trades_df.to_excel(

        file_name,

        index=False

    )

    return file_name
