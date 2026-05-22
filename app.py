import os
import time
from datetime import datetime, timedelta
from flask import Flask
import pandas as pd
from kiteconnect import KiteConnect

app = Flask(__name__)

# =========================
# ENV VARIABLES
# =========================

API_KEY = os.getenv("KITE_API_KEY", "").strip()

ACCESS_TOKEN = os.getenv(
    "KITE_ACCESS_TOKEN",
    ""
).strip()

# =========================
# BACKTEST ROUTE
# =========================

@app.route("/")
def run_backtest():

    # =========================
    # CONFIG CHECK
    # =========================

    if not API_KEY or not ACCESS_TOKEN:

        return """
        <h2 style='color:red;'>
        Missing KITE_API_KEY or KITE_ACCESS_TOKEN
        </h2>
        """

    try:

        # =========================
        # ZERODHA LOGIN
        # =========================

        kite = KiteConnect(api_key=API_KEY)

        kite.set_access_token(ACCESS_TOKEN)

        # =========================
        # VERIFY LOGIN
        # =========================

        try:

            profile = kite.profile()

            user_name = profile.get(
                "user_name",
                "Trader"
            )

        except Exception as auth_error:

            return f"""
            <h2 style='color:red;'>
            Zerodha Authentication Failed
            </h2>

            <p>{auth_error}</p>

            <p>
            Your access token probably expired.
            Generate a new token.
            </p>
            """

        # =========================
        # DATE RANGE
        # =========================

        final_end_date = (
            datetime.now()
            - timedelta(days=1)
        )

        final_start_date = (
            final_end_date
            - timedelta(days=365)
        )

        # =========================
        # SENSEX TOKEN
        # =========================

        instrument_token = 265779

        # =========================
        # DOWNLOAD DATA
        # =========================

        all_data = []

        current_start = final_start_date

        while current_start < final_end_date:

            current_end = min(
                current_start + timedelta(days=90),
                final_end_date
            )

            try:

                data = kite.historical_data(

                    instrument_token=instrument_token,

                    from_date=current_start,

                    to_date=current_end,

                    interval="5minute"
                )

                if data:

                    all_data.extend(data)

                time.sleep(0.5)

            except Exception as data_error:

                return f"""
                <h2 style='color:red;'>
                Historical Data Error
                </h2>

                <p>{data_error}</p>

                <p>
                Failed between:
                {current_start}
                and
                {current_end}
                </p>
                """

            current_start = (
                current_end
                + timedelta(days=1)
            )

        # =========================
        # EMPTY DATA CHECK
        # =========================

        if not all_data:

            return """
            <h2 style='color:red;'>
            No historical data returned
            </h2>

            <p>
            Check:
            </p>

            <ul>
                <li>Historical subscription</li>
                <li>Instrument token</li>
                <li>Access token</li>
            </ul>
            """

        # =========================
        # DATAFRAME
        # =========================

        df = pd.DataFrame(all_data)

        df["date"] = pd.to_datetime(df["date"])

        df = df.sort_values(
            "date"
        ).reset_index(drop=True)

        # =========================
        # EMA
        # =========================

        df["EMA9"] = df["close"].ewm(
            span=9,
            adjust=False
        ).mean()

        df["EMA21"] = df["close"].ewm(
            span=21,
            adjust=False
        ).mean()

        # =========================
        # VWAP
        # =========================

        df["date_only"] = df["date"].dt.date

        df["vol_price"] = (
            df["close"]
            * df["volume"]
        )

        df["cum_volume"] = df.groupby(
            "date_only"
        )["volume"].cumsum()

        df["cum_vol_price"] = df.groupby(
            "date_only"
        )["vol_price"].cumsum()

        df["VWAP"] = (
            df["cum_vol_price"]
            / df["cum_volume"]
        )

        # =========================
        # PREVIOUS VALUES
        # =========================

        df["prev_EMA9"] = df["EMA9"].shift(1)

        df["prev_EMA21"] = df["EMA21"].shift(1)

        # =========================
        # REMOVE NaN
        # =========================

        df = df.dropna().reset_index(drop=True)

        # =========================
        # MARKET TIME FILTER
        # =========================

        df["time"] = df["date"].dt.time

        market_start = datetime.strptime(
            "09:20",
            "%H:%M"
        ).time()

        market_end = datetime.strptime(
            "14:30",
            "%H:%M"
        ).time()

        df = df[
            (df["time"] >= market_start)
            &
            (df["time"] <= market_end)
        ].copy()

        # =========================
        # BACKTEST ENGINE
        # =========================

        trades = []

        current_position = None

        entry_price = 0

        entry_time = None

        for i in range(1, len(df)):

            row = df.iloc[i]

            close = row["close"]

            high = row["high"]

            low = row["low"]

            vwap = row["VWAP"]

            ema9 = row["EMA9"]

            ema21 = row["EMA21"]

            p_ema9 = row["prev_EMA9"]

            p_ema21 = row["prev_EMA21"]

            # =========================
            # SIGNALS
            # =========================

            buy_signal = (

                p_ema9 < p_ema21

                and

                ema9 > ema21

                and

                close > vwap

                and

                close > row["open"]
            )

            sell_signal = (

                p_ema9 > p_ema21

                and

                ema9 < ema21

                and

                close < vwap

                and

                close < row["open"]
            )

            # =========================
            # ENTRY
            # =========================

            if current_position is None:

                if buy_signal:

                    current_position = "BUY"

                    entry_price = close

                    entry_time = row["date"]

                elif sell_signal:

                    current_position = "SELL"

                    entry_price = close

                    entry_time = row["date"]

            # =========================
            # EXIT BUY
            # =========================

            elif current_position == "BUY":

                if sell_signal:

                    exit_price = close

                    pnl = exit_price - entry_price

                    trades.append({

                        "Type": "BUY",

                        "Entry Time": entry_time,

                        "Exit Time": row["date"],

                        "Entry": round(
                            entry_price,
                            2
                        ),

                        "Exit": round(
                            exit_price,
                            2
                        ),

                        "PnL": round(
                            pnl,
                            2
                        ),

                        "Return %": round(
                            (
                                pnl
                                / entry_price
                            ) * 100,
                            2
                        )
                    })

                    current_position = "SELL"

                    entry_price = close

                    entry_time = row["date"]

            # =========================
            # EXIT SELL
            # =========================

            elif current_position == "SELL":

                if buy_signal:

                    exit_price = close

                    pnl = entry_price - exit_price

                    trades.append({

                        "Type": "SELL",

                        "Entry Time": entry_time,

                        "Exit Time": row["date"],

                        "Entry": round(
                            entry_price,
                            2
                        ),

                        "Exit": round(
                            exit_price,
                            2
                        ),

                        "PnL": round(
                            pnl,
                            2
                        ),

                        "Return %": round(
                            (
                                pnl
                                / entry_price
                            ) * 100,
                            2
                        )
                    })

                    current_position = "BUY"

                    entry_price = close

                    entry_time = row["date"]

        # =========================
        # RESULTS
        # =========================

        trades_df = pd.DataFrame(trades)

        if trades_df.empty:

            return """
            <h2>
            No trades generated
            </h2>
            """

        total_trades = len(trades_df)

        wins = len(
            trades_df[
                trades_df["PnL"] > 0
            ]
        )

        losses = len(
            trades_df[
                trades_df["PnL"] <= 0
            ]
        )

        win_rate = (
            wins / total_trades
        ) * 100

        total_pnl = trades_df["PnL"].sum()

        total_return = trades_df[
            "Return %"
        ].fillna(0).sum()

        avg_win = trades_df[
            trades_df["PnL"] > 0
        ]["PnL"].mean()

        avg_loss = trades_df[
            trades_df["PnL"] <= 0
        ]["PnL"].mean()

        # =========================
        # EQUITY CURVE
        # =========================

        trades_df["Equity"] = (
            trades_df["PnL"].cumsum()
        )

        trades_df["Peak"] = trades_df[
            "Equity"
        ].cummax()

        trades_df["Drawdown"] = (

            trades_df["Equity"]

            -

            trades_df["Peak"]
        )

        max_drawdown = trades_df[
            "Drawdown"
        ].min()

        profit_factor = abs(

            trades_df[
                trades_df["PnL"] > 0
            ]["PnL"].sum()

            /

            trades_df[
                trades_df["PnL"] < 0
            ]["PnL"].sum()
        )

        # =========================
        # HTML REPORT
        # =========================

        return f"""

        <div style="
        font-family:sans-serif;
        max-width:700px;
        margin:auto;
        padding:30px;
        border-radius:10px;
        box-shadow:0 0 10px #ddd;
        ">

        <h1>
        📊 SENSEX BACKTEST REPORT
        </h1>

        <hr>

        <p>
        <b>User:</b>
        {user_name}
        </p>

        <p>
        <b>Period:</b>
        {final_start_date.date()}
        to
        {final_end_date.date()}
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
        <b>Total PnL:</b>
        {total_pnl:.2f}
        </p>

        <p>
        <b>Total Return:</b>
        {total_return:.2f}%
        </p>

        <p>
        <b>Average Win:</b>
        {avg_win:.2f}
        </p>

        <p>
        <b>Average Loss:</b>
        {avg_loss:.2f}
        </p>

        <p>
        <b>Profit Factor:</b>
        {profit_factor:.2f}
        </p>

        <p>
        <b>Max Drawdown:</b>
        {max_drawdown:.2f}
        </p>

        </div>
        """

    except Exception as global_error:

        return f"""
        <h2 style='color:red;'>
        Critical Error
        </h2>

        <p>{global_error}</p>
        """


# =========================
# RUN APP
# =========================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
