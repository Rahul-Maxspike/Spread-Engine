import os
import subprocess
import signal
import json
import threading
from datetime import datetime
from multiprocessing import shared_memory
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, render_template, request

# ========== XTS / MarketData Imports (Adjust these according to your project) ==========
from Connect import XTSConnect
from MarketDataSocketClient import MDSocket_io

# Create Flask app
app = Flask(__name__)

# ========== API Credentials & Initialization ==========
API_KEY = '0b84a5c57dcdf2b3a32261'
API_SECRET = 'Djya854$gm'
SOURCE = 'WebAPI'

xt = XTSConnect(API_KEY, API_SECRET, SOURCE)
login_response = xt.marketdata_login()  # Obtain token for MarketData
marketDataToken = login_response['result']['token']
muserID = login_response['result']['userID']

# Initialize the MarketData socket
soc = MDSocket_io(marketDataToken, muserID)

# ========== Load Instrument Mappings and Other JSON Files ==========
# Primary futures mapping (used for subscriptions)
with open('data/futures_mapping2.json', 'r') as f:
    instruments_mapping = json.load(f)

# Spread mapping (used for spread processing)
# If `spd` is indeed the same file but used differently, keep them separate
with open('data/futures_mapping2.json', 'r') as file:
    spd = json.load(file)

# Contract names
with open(r"data/contractnames.json", "r") as f:
    instrumentname = json.load(f)

# Lot sizes
with open(r'data/lotsize.json', 'r') as f:
    lotsizejson = json.load(f)

# Exchange instruments (if needed elsewhere)
with open(r"data/exchange_instruments2.json", "r") as f:
    Instruments = json.load(f)

# ========== Global Data Structures ==========
# List of subscriptions maintained in a JSON file
SUBSCRIPTIONS_FILE = 'data/subscriptions.json'
subscriptions = []
if os.path.exists(SUBSCRIPTIONS_FILE):
    with open(SUBSCRIPTIONS_FILE, 'r') as sub_file:
        subscriptions = json.load(sub_file)

# PID file path
PID_FILE = "data/fetching_pid.txt"

# Expiry dates (update as needed)
EXPIRY_DATES = [
    datetime.strptime("2025-02-28", "%Y-%m-%d"),
    datetime.strptime("2025-03-27", "%Y-%m-%d")
]

# Threading lock
datachanging_lock = threading.Lock()

# ========== Helper Functions ==========

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
    """Reads market data from shared memory and returns JSON."""
    try:
        shm = shared_memory.SharedMemory(name=f"shm_{exchange_id}")
        raw_data = bytes(shm.buf).rstrip(b"\x00").decode("utf-8")
        return json.loads(raw_data)
    except Exception as e:
        
        return None

def process_single_spread(spdid, instrumentname):
    """Process a single SPID's spread data from shared memory."""
    result = {}

    # Read spread data from shared memory
    spread_data = read_from_shm(spdid)
    if not spread_data:
        return {"error": f"SPID {spdid} not found in shared memory."}

    ltp = spread_data.get("Touchline", {}).get("LastTradedPrice")
    if ltp is None or not isinstance(ltp, (int, float)):
        return {"error": f"Invalid or missing LTP for SPID {spdid}"}

    result['LTP'] = ltp
    result['instrument_name'] = instrumentname.get(str(spdid), "Unknown Instrument")

    a1, b1 = 0, 0

    if str(spdid) in spd:
        result['related_spids'] = []
        related_spids = spd[str(spdid)]
        for i, related_spid in enumerate(related_spids):
            related_data = {
                'spid': related_spid,
                'instrument_name': instrumentname.get(str(related_spid), "Unknown Instrument")
            }
            related_spread_data = read_from_shm(related_spid)

            if related_spread_data:
                bids = related_spread_data.get("Bids", [])
                asks = related_spread_data.get("Asks", [])

                # Depending on LTP > 0 or 0, choose which side to read from
                if ltp > 0:
                    if i == 0 and asks:
                        a1 = asks[0].get("Price", 0) or 0
                        related_data['ask_price'] = a1
                    elif i == 1 and bids:
                        b1 = bids[0].get("Price", 0) or 0
                        related_data['bid_price'] = b1
                else:
                    if i == 0 and bids:
                        b1 = bids[0].get("Price", 0) or 0
                        related_data['bid_price'] = b1
                    elif i == 1 and asks:
                        a1 = asks[0].get("Price", 0) or 0
                        related_data['ask_price'] = a1
            else:
                related_data['error'] = 'Data not found in shared memory.'
                # If data is missing, you could skip or break. For now, skip.
                return None

            result['related_spids'].append(related_data)

        actual_spread = abs(b1 - a1)
        lot_size = lotsizejson.get(str(spdid), 0) or 0
        total_profit = actual_spread * lot_size

        result['spread'] = actual_spread
        result['profit'] = total_profit
        result['expiry_dates'] = [date.strftime("%Y-%m-%d") for date in EXPIRY_DATES]

    return result

def process_spread_data():
    """Process all spreads in `spd` and save the result to JSON."""
    result = {}
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(process_single_spread, int(spid), instrumentname): spid
            for spid in spd
        }
        for future in futures:
            spid = futures[future]
            try:
                result_data = future.result()
                if result_data:
                    result[spid] = result_data
                else:
                    result[spid] = {'error': f"SPID {spid} skipped due to missing data"}
            except Exception as e:
                result[spid] = {'error': str(e)}

    # Save processed data
    with open('processed_spread_data.json', 'w') as file:
        json.dump(result, file, indent=4)

    return {'message': 'Data processed and saved successfully'}

# ========== Routes ==========

@app.route('/')
def index():
    """Default route to render your main template."""
    return render_template('t4.html')

@app.route('/mdlist',methods=['POST'])
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
    """Subscribe to a particular key in instruments_mapping."""
    global subscriptions
    selected_key = request.json.get("key")
    if not selected_key or selected_key not in instruments_mapping:
        return jsonify({"error": "Invalid key"}), 400

    # Build subscription list
    subscription_list = [{
        "exchangeSegment": 2,
        "exchangeInstrumentID": int(selected_key)
    }]
    # Also add the mapped instruments
    for inst_id in instruments_mapping[selected_key]:
        subscription_list.append({
            "exchangeSegment": 2,
            "exchangeInstrumentID": inst_id
        })

    # Update and persist the subscriptions
    subscriptions.extend(subscription_list)
    with open(SUBSCRIPTIONS_FILE, 'w') as sub_file:
        json.dump(subscriptions, sub_file, indent=4)

    return jsonify({"message": "Subscription successful"})

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    """Unsubscribe a particular instrument ID along with its mapped IDs."""
    global subscriptions
    exchange_id = request.json.get("exchangeInstrumentID")
    if not exchange_id or exchange_id not in instruments_mapping:
        return jsonify({"error": "Invalid instrument ID"}), 400

    # Get all related instrument IDs
    instrument_list = [int(exchange_id)] + instruments_mapping.get(exchange_id, [])

    # Remove them from current subscriptions
    subscriptions = [
        sub for sub in subscriptions 
        if sub["exchangeInstrumentID"] not in instrument_list
    ]

    # Save updated subscriptions
    with open(SUBSCRIPTIONS_FILE, 'w') as sub_file:
        json.dump(subscriptions, sub_file, indent=4)

    return jsonify({"message": "Unsubscribed successfully"})

# ========== Market Data Fetching Process Management ==========

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
            ['start', 'cmd', '/k', f'title {TERMINAL_NAME} && python {SCRIPT_PATH}'], shell=True
        )
    else:
        # macOS/Linux (assuming gnome-terminal for demonstration)
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

# ========== Spread Data Processing Routes ==========

@app.route('/process-spread-data', methods=['GET'])
def process_and_store_spread_data():
    """Route to process the spread data and save to file."""
    response = process_spread_data()
    return jsonify(response)

@app.route('/get-spread-data', methods=['GET'])
def get_spread_data():
    """Retrieve processed spread data from file."""
    try:
        with open('processed_spread_data.json', 'r') as file:
            data = json.load(file)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'Data file not found. Please process the data first.'})

# ========== Main ==========
if __name__ == '__main__':
    app.run(debug=True, port=5001)
