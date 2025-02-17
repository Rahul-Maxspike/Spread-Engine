from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
import signal

from Connect import XTSConnect
from MarketDataSocketClient import MDSocket_io

app = Flask(__name__)

# MarketData API Credentials
API_KEY = '0b84a5c57dcdf2b3a32261'
API_SECRET = 'Djya854$gm'
SOURCE = 'WebAPI'

# Initialize the connection
xt = XTSConnect(API_KEY, API_SECRET, SOURCE)

with open("contractnames.json", "r") as file:
    instrumentname = json.load(file)

# Login for authorization token
response = xt.marketdata_login()
set_marketDataToken = response['result']['token']
set_muserID = response['result']['userID']

# Initialize market data socket
soc = MDSocket_io(set_marketDataToken, set_muserID)

# Load instrument mapping
with open('data/futures_mapping2.json') as f:
    instruments_mapping = json.load(f)

# Load existing subscriptions
subscriptions = []
if os.path.exists('data/subscriptions.json'):
    with open('data/subscriptions.json') as sub_file:
        subscriptions = json.load(sub_file)

# PID file path
PID_FILE = "data/fetching_pid.txt"


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


@app.route('/')
def index():
    subscriptions = []
    if os.path.exists('data/subscriptions.json'):
        with open('data/subscriptions.json') as sub_file:
            subscriptions = json.load(sub_file)
    subscriptions = [sub for sub in subscriptions if str(sub['exchangeInstrumentID']) in instruments_mapping]
    return render_template('index.html', keys=instruments_mapping.keys(), subscriptions=subscriptions, values=instrumentname)


@app.route('/subscribe', methods=['POST'])
def subscribe():
    selected_key = request.json.get("key")
    if not selected_key or selected_key not in instruments_mapping:
        return jsonify({"error": "Invalid key"}), 400

    # Create subscription list
    subscription_list = [{
        "exchangeSegment": 2,
        "exchangeInstrumentID": int(selected_key)
    }]
    for inst_id in instruments_mapping[selected_key]:
        subscription_list.append({
            "exchangeSegment": 2,
            "exchangeInstrumentID": inst_id
        })

    # Store subscriptions
    subscriptions.extend(subscription_list)
    with open('data/subscriptions.json', 'w') as sub_file:
        json.dump(subscriptions, sub_file, indent=4)

    return jsonify({"message": "Subscription successful", "response": response})


@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    exchange_id = request.json.get("exchangeInstrumentID")
    if not exchange_id or exchange_id not in instruments_mapping:
        return jsonify({"error": "Invalid instrument ID"}), 400

    # Get all related instrument IDs from the mapping
    instrument_list = [int(exchange_id)] + instruments_mapping.get(exchange_id, [])

    # Remove all related instrument IDs from subscriptions
    global subscriptions
    subscriptions = [sub for sub in subscriptions if sub["exchangeInstrumentID"] not in instrument_list]

    # Save the updated subscriptions
    with open('data/subscriptions.json', 'w') as sub_file:
        json.dump(subscriptions, sub_file, indent=4)

    return jsonify({"message": "Unsubscribed successfully"})


# Market Data Fetching Process Management
SCRIPT_PATH = os.path.join(os.getcwd(), "MDEngine.py")
TERMINAL_NAME = "MarketDataTerminal"


@app.route('/start_fetching', methods=['POST'])
def start_fetching():
    if get_pid() is not None:
        return jsonify({"message": "Market data fetching is already running!"})

    if os.name == 'nt':  # Windows
        # Start Command Prompt with a specific title and run the script
        process = subprocess.Popen(
            ['start', 'cmd', '/k', f'title {TERMINAL_NAME} && python {SCRIPT_PATH}'], shell=True
        )
    elif os.name == 'posix':  # macOS/Linux
        # Start terminal with a specific name
        process = subprocess.Popen(
            ['gnome-terminal', '--title=' + TERMINAL_NAME, '--', 'python3', SCRIPT_PATH], preexec_fn=os.setsid
        )

    save_pid(process.pid)
    return jsonify({"message": "Started fetching market data!", "pid": process.pid})


@app.route('/stop_fetching', methods=['POST'])
def stop_fetching():
    pid = get_pid()
    if pid is None:
        return jsonify({"message": "Market data fetching is not running!"})

    if os.name == 'nt':  # Windows
        # Kill all terminals with the specific title
        subprocess.call(['taskkill', '/F', '/FI', f'WINDOWTITLE eq {TERMINAL_NAME}*'], shell=True)
    elif os.name == 'posix':  # macOS/Linux
        # Kill all terminals running with the specific name
        subprocess.call(["pkill", "-f", f"gnome-terminal.*{TERMINAL_NAME}"])

    delete_pid()
    return jsonify({"message": "Stopped fetching market data!"})


if __name__ == '__main__':
    app.run(debug=True)
