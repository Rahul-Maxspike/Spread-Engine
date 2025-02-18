import os
import subprocess
import signal
import json
import threading
from datetime import datetime
from multiprocessing import shared_memory
from concurrent.futures import ThreadPoolExecutor
from OrderManager import OrderManager 
from flask import Flask, jsonify, render_template, request

# ========== XTS / MarketData Imports (Adjust these according to your project) ==========
# Example: from Connect import XTSConnect
# Example: from MarketDataSocketClient import MDSocket_io

# If you don't use these, remove or comment them out.
from Connect import XTSConnect
from MarketDataSocketClient import MDSocket_io

# ------------------------------------------------------------------------------
# SpreadEntryManager import
# ------------------------------------------------------------------------------
from EntryManager import SpreadEntryManager

# ------------------------------------------------------------------------------
# Flask app initialization
# ------------------------------------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------------------------------------
# API Credentials & XTS Initialization (Adjust to your real credentials)
# ------------------------------------------------------------------------------
API_KEY = '0b84a5c57dcdf2b3a32261'
API_SECRET = 'Djya854$gm'
SOURCE = 'WebAPI'

xt = XTSConnect(API_KEY, API_SECRET, SOURCE)
login_response = xt.marketdata_login()  # Obtain token for MarketData
marketDataToken = login_response['result']['token']
muserID = login_response['result']['userID']

# Initialize the MarketData socket (if you actually use socket connection)
soc = MDSocket_io(marketDataToken, muserID)

# ------------------------------------------------------------------------------
# Load JSON Files
# ------------------------------------------------------------------------------
# 1) Primary futures mapping
with open('data/futures_mapping2.json', 'r') as f:
    instruments_mapping = json.load(f)

# 2) Spread mapping (same JSON, but used differently)
with open('data/futures_mapping2.json', 'r') as file:
    spd = json.load(file)

# 3) Instrument names
with open(r"data/contractnames.json", "r") as f:
    instrumentname = json.load(f)

# 4) Lot sizes
with open(r'data/lotsize.json', 'r') as f:
    lotsizejson = json.load(f)

# 5) Exchange instruments (if needed)
with open(r"data/exchange_instruments2.json", "r") as f:
    Instruments = json.load(f)

# ------------------------------------------------------------------------------
# Global Data Structures
# ------------------------------------------------------------------------------
SUBSCRIPTIONS_FILE = 'data/subscriptions.json'
subscriptions = []
if os.path.exists(SUBSCRIPTIONS_FILE):
    with open(SUBSCRIPTIONS_FILE, 'r') as sub_file:
        subscriptions = json.load(sub_file)

# PID management
PID_FILE = "data/fetching_pid.txt"

# Example expiry dates
EXPIRY_DATES = [
    datetime.strptime("2025-02-28", "%Y-%m-%d"),
    datetime.strptime("2025-03-27", "%Y-%m-%d")
]

# Lock for data manipulation
datachanging_lock = threading.Lock()

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

def save_pid(pid):
    """Save process ID to a file."""
    with open(PID_FILE, "w") as f:
        f.write(str(pid))

def get_pid():
    """Retrieve process ID from the file."""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None

def delete_pid():
    """Delete the PID file."""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

def read_from_shm(exchange_id):
    """
    Reads market data from shared memory and returns JSON.
    Returns None if shared memory is unavailable or data cannot be parsed.
    """
    try:
        shm = shared_memory.SharedMemory(name=f"shm_{exchange_id}")
        raw_data = bytes(shm.buf).rstrip(b"\x00").decode("utf-8")
        return json.loads(raw_data)
    except Exception:
        return None

# ------------------------------------------------------------------------------
# SpreadEntryManager instance
# ------------------------------------------------------------------------------
entry_manager = SpreadEntryManager(csv_file='spread_positions.csv')

# ------------------------------------------------------------------------------
# Process Single Spread Function (Updated to handle +/- LTP)
# ------------------------------------------------------------------------------
def process_single_spread(spdid, instrumentname):
    """
    Process a single SPID's spread data from shared memory,
    determining buy_leg vs. sell_leg based on the sign of LTP.
    """
    result = {}

    # 1) Read primary SPID data
    spread_data = read_from_shm(spdid)
    if not spread_data:
        return {"error": f"SPID {spdid} not found in shared memory."}

    # 2) Extract LTP
    ltp = spread_data.get("Touchline", {}).get("LastTradedPrice")
    if ltp is None or not isinstance(ltp, (int, float)):
        return {"error": f"Invalid or missing LTP for SPID {spdid}"}

    result['LTP'] = ltp
    result['instrument_name'] = instrumentname.get(str(spdid), "Unknown Instrument")

    # 3) Check that spdid is in our spd mapping
    if str(spdid) not in spd:
        return {"error": f"No spread mapping for SPID {spdid} in spd."}

    related_spids = spd[str(spdid)]
    if len(related_spids) != 2:
        return {"error": f"SPID {spdid} has {len(related_spids)} related spids. Expected 2."}

    # 4) Based on the sign of LTP, decide which spid is buy_leg vs. sell_leg
    if ltp > 0:
        buy_leg = related_spids[0]
      
        sell_leg = related_spids[1]
    else:
        buy_leg = related_spids[1]
        sell_leg = related_spids[0]

    # 5) Read each leg's shared memory
    buy_data = read_from_shm(buy_leg)

    sell_data = read_from_shm(sell_leg)
    if not buy_data or not sell_data:
        return {
            "error": "Missing data for one or both legs",
            "buy_leg_data_found": bool(buy_data),
            "sell_leg_data_found": bool(sell_data)
        }

    # 6) Extract best Ask for the buy_leg
    buy_asks = buy_data.get("Asks", [])
    if buy_asks:
        buy_ask_price = buy_asks[0].get("Price", 0)
    else:
        buy_ask_price = 0

    # 7) Extract best Bid for the sell_leg
    sell_bids = sell_data.get("Bids", [])
    if sell_bids:
        sell_bid_price = sell_bids[0].get("Price", 0)
    else:
        sell_bid_price = 0

    # 8) Compute an example "actual_spread"
    actual_spread = abs(sell_bid_price - buy_ask_price)
    lot_size = lotsizejson.get(str(spdid), 0) or 0
    total_profit_estimate = actual_spread * lot_size
    buy_instrument_name = instrumentname.get(str(buy_leg), "Unknown")
    sell_instrument_name = instrumentname.get(str(sell_leg), "Unknown")

    # 9) Populate result dict
    result.update({
        "buy_leg": buy_leg,
        "sell_leg": sell_leg,
        "buy_ask_price": buy_ask_price,
        "sell_bid_price": sell_bid_price,
        "buyInstrumentName":buy_instrument_name,
        "sellInstrumentName":sell_instrument_name,
        "spread": actual_spread,
        "profit": total_profit_estimate,
        "expiry_dates": [d.strftime("%Y-%m-%d") for d in EXPIRY_DATES],
    })

    # 10) Example condition to create a new position
    #     (You can adapt the logic as you wish; this is just a sample.)
    if (abs(ltp) > actual_spread) and (ltp != 0):
        buy_instrument_name = instrumentname.get(str(buy_leg), "Unknown")
        sell_instrument_name = instrumentname.get(str(sell_leg), "Unknown")

        entry_manager.create_position(
            spread_id=spdid,
            buy_ticker_id=buy_leg,
            buy_ticker_name=buy_instrument_name,
            buy_quantity=lot_size,
            buy_entry_price=buy_ask_price,
            sell_ticker_id=sell_leg,
            sell_ticker_name=sell_instrument_name,
            sell_quantity=lot_size,
            sell_entry_price=sell_bid_price
        )

    return result

# ------------------------------------------------------------------------------
# Process All Spreads Function
# ------------------------------------------------------------------------------
def process_spread_data():
    """
    Process all spreads listed in `spd` and save results to JSON.
    """
    result = {}
    with ThreadPoolExecutor() as executor:
        futures_map = {
            executor.submit(process_single_spread, int(spid), instrumentname): spid
            for spid in spd
        }
        for future in futures_map:
            spid = futures_map[future]
            try:
                result_data = future.result()
                if result_data:
                    result[spid] = result_data
                else:
                    result[spid] = {'error': f"SPID {spid} returned no data"}
            except Exception as e:
                result[spid] = {'error': str(e)}

    # Save processed data
    with open('processed_spread_data.json', 'w') as file:
        json.dump(result, file, indent=4)

    return {'message': 'Data processed and saved successfully'}

# ------------------------------------------------------------------------------
# Flask Routes
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    """Default route to render your main template."""
    return render_template('t4.html')

@app.route('/mdlist', methods=['POST'])
def mdlist():
    """Show currently subscribed instruments."""
    current_subs = []
    if os.path.exists(SUBSCRIPTIONS_FILE):
        with open(SUBSCRIPTIONS_FILE) as sub_file:
            current_subs = json.load(sub_file)

    # Filter only those in instruments_mapping
    current_subs = [
        sub for sub in current_subs
        if str(sub['exchangeInstrumentID']) in instruments_mapping
    ]
    return render_template(
        'index.html',
        keys=instruments_mapping.keys(),
        subscriptions=current_subs,
        values=instrumentname
    )

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """
    Subscribe to a particular key in instruments_mapping.
    Expects JSON: {"key": <some_instrument_key>}
    """
    global subscriptions
    selected_key = request.json.get("key")
    if not selected_key or selected_key not in instruments_mapping:
        return jsonify({"error": "Invalid key"}), 400

    # Build subscription list
    subscription_list = [{
        "exchangeSegment": 2,
        "exchangeInstrumentID": int(selected_key)
    }]
    # Also add mapped instruments
    for inst_id in instruments_mapping[selected_key]:
        subscription_list.append({
            "exchangeSegment": 2,
            "exchangeInstrumentID": inst_id
        })

    # Update subscriptions in memory
    subscriptions.extend(subscription_list)

    # Persist to file
    with open(SUBSCRIPTIONS_FILE, 'w') as sub_file:
        json.dump(subscriptions, sub_file, indent=4)

    return jsonify({"message": "Subscription successful"})

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    """Unsubscribe a particular instrument ID + its mapped IDs."""
    global subscriptions
    exchange_id = request.json.get("exchangeInstrumentID")
    if not exchange_id or exchange_id not in instruments_mapping:
        return jsonify({"error": "Invalid instrument ID"}), 400

    # Get all related instrument IDs
    instrument_list = [int(exchange_id)] + instruments_mapping.get(exchange_id, [])
    # Filter them out
    subscriptions = [
        sub for sub in subscriptions
        if sub["exchangeInstrumentID"] not in instrument_list
    ]

    with open(SUBSCRIPTIONS_FILE, 'w') as sub_file:
        json.dump(subscriptions, sub_file, indent=4)

    return jsonify({"message": "Unsubscribed successfully"})

# ------------------------------------------------------------------------------
# Market Data Fetching Process Management
# ------------------------------------------------------------------------------
SCRIPT_PATH = os.path.join(os.getcwd(), "MDEngine.py")
TERMINAL_NAME = "MarketDataTerminal"

@app.route('/start_fetching', methods=['POST'])
def start_fetching():
    """Start market data fetching in a new terminal/process."""
    if get_pid() is not None:
        return jsonify({"message": "Market data fetching is already running!"})

    if os.name == 'nt':  # Windows
        # Start Command Prompt with a specific title and run the script
        process = subprocess.Popen(
            ['start', 'cmd', '/k', f'title {TERMINAL_NAME} && python {SCRIPT_PATH}'],
            shell=True
        )
    else:
        # macOS/Linux (example using gnome-terminal; adjust for your environment)
        process = subprocess.Popen(
            ['gnome-terminal', '--title=' + TERMINAL_NAME, '--', 'python3', SCRIPT_PATH],
            preexec_fn=os.setsid
        )

    save_pid(process.pid)
    return jsonify({"message": "Started fetching market data!", "pid": process.pid})

@app.route('/stop_fetching', methods=['POST'])
def stop_fetching():
    """Stop market data fetching by killing the associated terminal."""
    pid = get_pid()
    if pid is None:
        return jsonify({"message": "Market data fetching is not running!"})

    if os.name == 'nt':  # Windows
        subprocess.call(['taskkill', '/F', '/FI', f'WINDOWTITLE eq {TERMINAL_NAME}*'], shell=True)
    else:
        subprocess.call(["pkill", "-f", f"gnome-terminal.*{TERMINAL_NAME}"])

    delete_pid()
    return jsonify({"message": "Stopped fetching market data!"})

# ------------------------------------------------------------------------------
# Spread Data Processing Routes
# ------------------------------------------------------------------------------
@app.route('/process-spread-data', methods=['GET'])
def process_and_store_spread_data():
    """
    Route to process the spread data for each SPID, then store results in JSON.
    """
    response = process_spread_data()
    return jsonify(response)

@app.route('/get-spread-data', methods=['GET'])
def get_spread_data():
    """
    Retrieve processed spread data from file.
    """
    try:
        with open('processed_spread_data.json', 'r') as file:
            data = json.load(file)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'Data file not found. Please process the data first.'})

# ------------------------------------------------------------------------------
# Live Positions (from CSV + shared memory) Routes
# ------------------------------------------------------------------------------
@app.route('/positions/live', methods=['GET'])
def get_live_positions():
    """
    Reads all open positions from the CSV (spread_positions.csv),
    fetches live prices from shared memory, computes current P/L,
    and returns as JSON.
    """
    positions = entry_manager._load_positions()
    live_positions = []

    for pos in positions:
        spread_id = pos['spread_id']
        buy_ticker_id = pos['buy_ticker_id']
        sell_ticker_id = pos['sell_ticker_id']
        buy_ticker_name = pos["buy_ticker_name"]
        sell_ticker_name = pos["sell_ticker_name"]

        buy_entry_price = float(pos['buy_entry_price']) if pos['buy_entry_price'] else 0.0
        sell_entry_price = float(pos['sell_entry_price']) if pos['sell_entry_price'] else 0.0
        buy_qty = float(pos['buy_quantity']) if pos['buy_quantity'] else 0.0
        sell_qty = float(pos['sell_quantity']) if pos['sell_quantity'] else 0.0

        # Get the current price from shared memory
        buy_data = read_from_shm(buy_ticker_id)
        sell_data = read_from_shm(sell_ticker_id)

        buy_ltp = None
        sell_ltp = None
        if buy_data and "Touchline" in buy_data:
            buy_ltp = buy_data["Touchline"].get("LastTradedPrice")
        if sell_data and "Touchline" in sell_data:
            sell_ltp = sell_data["Touchline"].get("LastTradedPrice")

        if buy_ltp is None or sell_ltp is None:
            # If no LTP found, skip or treat as 0
            continue

        # Calculate live PnL:
        #   Buy PnL = (current buy price - buy_entry_price) * buy_qty
        #   Sell PnL = (sell_entry_price - current sell price) * sell_qty
        buy_pnl = (buy_ltp - buy_entry_price) * buy_qty
        sell_pnl = (sell_entry_price - sell_ltp) * sell_qty
        total_pnl = buy_pnl + sell_pnl

        live_positions.append({
            "spread_id": spread_id,
            "buy_ticker_id": buy_ticker_id,
            "sell_ticker_id": sell_ticker_id,
            "buy_ticker_name": buy_ticker_name,
            "sell_ticker_name": sell_ticker_name,
            "buy_ltp": buy_ltp,
            "sell_ltp": sell_ltp,
            "buy_entry_price": buy_entry_price,
            "sell_entry_price": sell_entry_price,
            "buy_quantity": buy_qty,
            "sell_quantity": sell_qty,
            "live_buy_pnl": round(buy_pnl, 2),
            "live_sell_pnl": round(sell_pnl, 2),
            "live_total_pnl": round(total_pnl, 2)
        })

    return jsonify(live_positions)

@app.route('/positions', methods=['GET'])
def live_positions_view():
    """
    Returns the front-end page (HTML) that displays live positions.
    """
    return render_template('positions_live.html')


# ------------------------------------------------------------------------------
#PLACE Order
# ------------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Import the new OrderManager class
# ---------------------------------------------------------------------------
from OrderManager import OrderManager  # Adjust the path as needed

# ---------------------------------------------------------------------------
# New Flask route for placing orders
# ---------------------------------------------------------------------------
@app.route('/place-order', methods=['POST'])
def place_order():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON payload received"}), 400

    # Just for debugging, you can print or write the order to a file
    print("Order received:", data)


    buy_ticker_id = data.get("buy_ticker_id")
    sell_ticker_id = data.get("sell_ticker_id")
    buy_quantity = data.get("buy_quantity")
    sell_quantity = data.get("sell_quantity")
    buy_price = data.get("buy_price")
    sell_price = data.get("sell_price")
    quantity=buy_quantity*lotsizejson.get(str(buy_ticker_id),0)

    orders={
  "orders": [
    {
      "exchangeSegment": "NSEFO",
      "exchangeInstrumentId": buy_ticker_id,
      "orderType": "LIMIT",
      "orderSide": "BUY",
      "orderValidity": "1",
      "quantity": quantity,
      "price": buy_price,
      "clientId": "MaxXTSJY2802",
      "strategyId": "Spread"
    },
    {
      "exchangeSegment": "NSEFO",
      "exchangeInstrumentId": sell_ticker_id,
      "orderType": "LIMIT",
      "orderSide": "BUY",
      "orderValidity": "1",
      "quantity": quantity,
      "price": sell_price,
      "clientId": "MaxXTSJY2802",
      "strategyId": "Spread"
    },  ],
"clientId": "MaxXTSJY2802",
      "strategyId": "Spread"
}
    

    with open("placeorder.json", "w") as f:
       json.dump(orders, f)
    # Additional validation logic or actual order logic...
    #return jsonify({"message": "Order was placed (dummy response)"}), 200
    # 2) Create an OrderManager instance (use default or custom URL)
    order_manager = OrderManager() 

   
    result = order_manager.placeorder_basket(
        buy_ticker_id=buy_ticker_id,
        buy_quantity=quantity,
        buy_price=buy_price,
        sell_ticker_id=sell_ticker_id,
        sell_quantity=quantity,
        sell_price=sell_price,
        exchange_segment="NSEFO",
        order_type="LIMIT",
        order_validity="1",
        client_id="MaxXTSJY2802",
        strategy_id="Spread"
    )



    # 4) Return JSON response to the client
    status_code = result.get("status_code", 200)  # Extract from result
    return jsonify(result), status_code




# ------------------------------------------------------------------------------
# Run the Flask app
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5001)
