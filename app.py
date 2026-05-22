import os
from flask import Flask, request

app = Flask(__name__)

API_KEY = os.getenv("KITE_API_KEY", "").strip()
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "").strip()

@app.route("/")
def home():
    # 1. Check if the user is logging in right now
    req_token = request.args.get("request_token")
    if req_token:
        return f"""
        <div style="font-family: sans-serif; padding: 30px; max-width: 600px; margin: auto; border: 1px solid #ced4da; border-radius: 8px; background-color: #e3f2fd;">
            <h2 style="color: #0d47a1; margin-top:0;">🔑 Request Token Captured!</h2>
            <p>Your app successfully routed back from Zerodha.</p>
            <p><b>Your raw Request Token is:</b></p>
            <div style="background: #fff; padding: 15px; border-radius: 4px; border: 1px solid #90caf9; font-family: monospace; font-size: 16px; word-break: break-all; color: #1565c0;">
                {req_token}
            </div>
            <p style="margin-bottom:0; margin-top:15px; color:#555;">👉 Copy that string, paste it back to our chat, and we will activate your system.</p>
        </div>
        """

    # 2. Base Dashboard display when no token is present
    return f"""
    <div style="font-family: sans-serif; padding: 30px; max-width: 600px; margin: auto; border: 1px solid #ccc; border-radius: 8px; text-align: center; margin-top: 50px;">
        <h2 style="color: #2c3e50;">🤖 SENSEX Bot Standby Mode</h2>
        <p style="color: #7f8c8d;">The web server is live, stable, and listening safely on Render.</p>
        <hr style="border:0; border-top: 1px solid #eee; margin: 20px 0;">
        <p>Current API Key Loaded: <b>{"✅ Yes" if API_KEY else "❌ Missing"}</b></p>
        <p>Current Access Token Loaded: <b>{"✅ Yes" if ACCESS_TOKEN else "❌ Missing"}</b></p>
    </div>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
