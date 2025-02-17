import csv
import json
import os
from Connect import XTSConnect
from multiprocessing import shared_memory
from MarketDataSocketClient import MDSocket_io

# MarketData API Credentials
API_KEY = '0b84a5c57dcdf2b3a32261'
API_SECRET = 'Djya854$gm'
SOURCE = 'WebAPI'

# Initialize the connection
xt = XTSConnect(API_KEY, API_SECRET, SOURCE)

# Login for authorization token
response = xt.marketdata_login()
print("Login:", response)

# Store the token and user ID
set_marketDataToken = response['result']['token']
set_muserID = response['result']['userID']
print("Login:", response)

soc = MDSocket_io(set_marketDataToken, set_muserID)

# Read the instrument mapping JSON file.
# Example structure:
# {
#   "9973982": [38805, 39902],
#   "10010573": [38946, 40397],
#   "10150273": [39363, 73345]
# }
with open(r'data\futures_mapping2.json') as f:
    instruments_mapping = json.load(f)

# Create a subscription list from the mapping.
# Each value in the mapping corresponds to an exchangeInstrumentID.
# We assign a default exchangeSegment value (e.g., 2) for each instrument.
subscription_list = []
MAX_INSTRUMENTS = 100

for key, id_list in instruments_mapping.items():
    for inst_id in id_list:
        subscription_list.append({
            "exchangeSegment": 2,           # Default exchange segment (adjust as needed)
            "exchangeInstrumentID": inst_id
        })
        if len(subscription_list) >= MAX_INSTRUMENTS:
            break
    if len(subscription_list) >= MAX_INSTRUMENTS:
        break

print(f"Subscribing to {len(subscription_list)} instruments.")

def on_connect():
    """Connect to the socket and send a subscription request with the selected instruments."""
    print('Market Data Socket connected successfully!')
    print('Sending subscription request for the following instruments:')
    print(subscription_list)
    # Send a single subscription request with the subscription list
    response = xt.send_subscription(subscription_list, 1502)
    print('Sent Subscription request!')
    print("Subscription response:", response)

# Dictionary to hold shared memory references for each instrument
shm_dict = {}

# Define shared memory size (adjust if necessary)
SHM_SIZE = 4096

def create_shared_memory(exchange_id):
    """Creates a shared memory segment for a given ExchangeInstrumentID."""
    try:
        if exchange_id not in shm_dict:
            shm = shared_memory.SharedMemory(name=f"shm_{exchange_id}", create=True, size=SHM_SIZE)
            shm_dict[exchange_id] = shm
            print(f"✅ Created shared memory for {exchange_id}")
        else:
            print(f"⚠️ Shared memory already exists for {exchange_id}")
    except FileExistsError:
        print(f"⚠️ Shared memory already exists for {exchange_id}")
        shm = shared_memory.SharedMemory(name=f"shm_{exchange_id}")
        shm_dict[exchange_id] = shm

def write_to_shm(exchange_id, data):
    """Writes market data to the shared memory segment."""
    if exchange_id not in shm_dict:
        create_shared_memory(exchange_id)

    shm = shm_dict[exchange_id]
    encoded_data = json.dumps(data).encode("utf-8")

    if len(encoded_data) > SHM_SIZE:
        print(f"⚠️ Warning: Data for {exchange_id} exceeds shared memory size and will be truncated.")

    # Write data to shared memory and clear any remaining buffer space
    shm.buf[:len(encoded_data)] = encoded_data
    shm.buf[len(encoded_data):] = b'\x00' * (SHM_SIZE - len(encoded_data))

def on_message1502(data):
    """Callback function for handling full market data."""
    print(data)
    try:
        data_dict = json.loads(data)
        exchange_id = str(data_dict.get("ExchangeInstrumentID"))
        if exchange_id:
            write_to_shm(exchange_id, data_dict)
            print(f"✅ Updated shared memory for {exchange_id}")
        else:
            print("⚠️ ExchangeInstrumentID missing in received data")
    except json.JSONDecodeError:
        print("❌ Error: Received invalid JSON data")

def on_disconnect():
    print('Market Data Socket disconnected!')

def on_error(data):
    print('Market Data Error:', data)

# Set socket event callbacks
soc.on_connect = on_connect
soc.on_message1502_json_full = on_message1502

el = soc.get_emitter()
el.on('connect', on_connect)
el.on('1502-json-full', on_message1502)

# Connect to the market data socket
soc.connect()
