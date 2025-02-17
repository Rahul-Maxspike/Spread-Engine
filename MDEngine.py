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

# Initialize
xt = XTSConnect(API_KEY, API_SECRET, SOURCE)

# Login for authorization token
response = xt.marketdata_login()
print("Login: ", response)

# Store the token and userid
set_marketDataToken = response['result']['token']
set_muserID = response['result']['userID']
print("Login: ", response)

soc = MDSocket_io(set_marketDataToken, set_muserID)

# Read instrument list from JSON
with open(r'data\exchange_instruments.json') as f:
    Instruments = json.load(f)


def on_connect():
    """Connect to the socket."""
    print('Market Data Socket connected successfully!')
    print('Sending subscription request for Instruments - \n' + str(Instruments))
    response = xt.send_subscription(Instruments, 1502)
    print('Sent Subscription request!')
    print("Subscription response: ", response)


shm_dict = {}

# Define shared memory size
SHM_SIZE = 4096  # Adjust based on expected data size


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

    # Write data to shared memory
    shm.buf[: len(encoded_data)] = encoded_data
    shm.buf[len(encoded_data):] = b'\x00' * (SHM_SIZE - len(encoded_data))  # Clear extra space



# Handle incoming message

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
    print('Market Data Error', data)

soc.on_connect = on_connect
soc.on_message1502_json_full = on_message1502

el = soc.get_emitter()
el.on('connect', on_connect)
el.on('1502-json-full', on_message1502)

soc.connect()
