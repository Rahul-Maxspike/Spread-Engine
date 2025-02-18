import csv
import json
import os
import time
from Connect import XTSConnect
from multiprocessing import shared_memory
from MarketDataSocketClient import MDSocket_io

########################################################################
# MarketData API Credentials
########################################################################
API_KEY = '0b84a5c57dcdf2b3a32261'
API_SECRET = 'Djya854$gm'
SOURCE = 'WebAPI'

########################################################################
# Global variables
########################################################################
xt = None                 # Will hold the XTSConnect instance
current_soc = None        # Will hold the current MDSocket_io instance
shm_dict = {}             # Tracks shared memory for each ExchangeInstrumentID
SHM_SIZE = 4096           # Adjust based on expected data size
Instruments = []          # Will hold the list of instruments from JSON
set_marketDataToken = ''  # Current MarketData token
set_muserID = ''          # Current user ID

########################################################################
# Step 1: Helper functions for shared memory
########################################################################
def create_shared_memory(exchange_id):
    """Creates a shared memory segment for a given ExchangeInstrumentID."""
    try:
        if exchange_id not in shm_dict:
            shm = shared_memory.SharedMemory(
                name=f"shm_{exchange_id}", 
                create=True, 
                size=SHM_SIZE
            )
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
    shm.buf[:len(encoded_data)] = encoded_data
    # Clear out any leftover data
    shm.buf[len(encoded_data):] = b'\x00' * (SHM_SIZE - len(encoded_data))

########################################################################
# Step 2: Socket event handlers
########################################################################
def on_connect():
    """Called when the socket is connected."""
    print("Market Data Socket connected successfully!")
    print("Sending subscription request for instruments:\n", Instruments)

    # Send subscription
    response = xt.send_subscription(Instruments, 1502)
    print("Subscription response:", response)

def on_message1502(data):
    """Callback function for handling full market data (event 1502-json-full)."""
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
    """
    Called when the socket is disconnected.
    We create a brand new MDSocket_io client and reconnect.
    """
    global current_soc

    print("Market Data Socket disconnected! Attempting to reconnect in 5 seconds...")
    time.sleep(5)
    try:
        # If token might have expired, re-login:
        response = xt.marketdata_login()
        new_token = response['result']['token']
        new_userID = response['result']['userID']
        print("Login Response (re-login):", response)

        # Create a brand new socket instance
        current_soc = create_new_socket(new_token, new_userID)
        current_soc.connect()
        print("Reconnect attempt done with a new socket instance.")
    except Exception as e:
        print(f"Reconnection failed: {e}")

def on_error(data):
    """Called when there's an error event from the server."""
    print("Market Data Error:", data)

########################################################################
# Step 3: Helper function to create/bind a new MDSocket_io
########################################################################
def create_new_socket(token, user_id):
    """
    Creates a new MDSocket_io object, binds all event handlers,
    and returns the object.
    """
    soc = MDSocket_io(token, user_id)

    # Assign the "shortcut" handlers
    soc.on_connect = on_connect
    soc.on_message1502_json_full = on_message1502

    # If you need the emitter directly, get it:
    el = soc.get_emitter()
    el.on('connect', on_connect)
    el.on('1502-json-full', on_message1502)
    el.on('disconnect', on_disconnect)
    el.on('error', on_error)

    return soc

########################################################################
# Step 4: Main routine
########################################################################
def main():
    global xt, current_soc, set_marketDataToken, set_muserID, Instruments

    # 1. Initialize XTSConnect
    xt = XTSConnect(API_KEY, API_SECRET, SOURCE)

    # 2. Login for the MarketData token
    response = xt.marketdata_login()
    print("Login Response:", response)

    # 3. Extract token / userID
    set_marketDataToken = response['result']['token']
    set_muserID = response['result']['userID']

    # 4. Read instrument list from JSON
    with open(r'data\exchange_instruments2.json') as f:
        Instruments = json.load(f)

    # 5. Create and connect the socket
    current_soc = create_new_socket(set_marketDataToken, set_muserID)
    current_soc.connect()

    # At this point, the socket is connected and listening.
    # If the connection drops, `on_disconnect` will be triggered,
    # which will create a new socket instance and reconnect automatically.

    # 6. Optionally keep the main thread alive, do other tasks, etc.
    while True:
        time.sleep(1)

########################################################################
# Entry point
########################################################################
if __name__ == "__main__":
    main()
