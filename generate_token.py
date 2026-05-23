from kiteconnect import KiteConnect

# ==========================================
# YOUR API DETAILS
# ==========================================

api_key = "i2c07s753rdi06u5"

api_secret = "i8pmxc6eij1kz07isa6qmk1br3y7nimc"

# ==========================================
# CREATE KITE OBJECT
# ==========================================

kite = KiteConnect(
    api_key=api_key
)

# ==========================================
# LOGIN URL
# ==========================================

print("\nOpen this URL in browser:\n")

print(
    kite.login_url()
)

# ==========================================
# ENTER REQUEST TOKEN
# ==========================================

request_token = input(
    "\nPaste request_token here: "
)

# ==========================================
# GENERATE ACCESS TOKEN
# ==========================================

data = kite.generate_session(
    request_token,
    api_secret=api_secret
)

access_token = data[
    "access_token"
]

print("\n========================")
print("ACCESS TOKEN")
print("========================\n")

print(access_token)

print("\n========================")
