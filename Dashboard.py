from flask import Flask, jsonify, render_template
import json
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime
from multiprocessing import shared_memory

app = Flask(__name__)

# Define the spd dictionary
#spd = {10931994: [42541, 41498], 10559186: [41094, 39122]}
with open(r'data\futures_mapping.json', 'r') as file:
    spd = json.load(file)
datachanging_lock = threading.Lock()

EXPIRY_DATES = [
    datetime.strptime("2025-02-28", "%Y-%m-%d"),
    datetime.strptime("2025-03-27", "%Y-%m-%d")
]

# Load instrument data
with open("Titaninstrument_list.json") as f:
    Instruments = json.load(f)

with open('ExchangeInstrumentID.json', 'r') as file:
    instrumentname = json.load(file)

def read_from_shm(exchange_id):
    """Reads market data from shared memory and returns JSON."""
    try:
        shm = shared_memory.SharedMemory(name=f"shm_{exchange_id}")
        raw_data = bytes(shm.buf).rstrip(b"\x00").decode("utf-8")
        return json.loads(raw_data)
    except Exception as e:
        print(f"Error reading shared memory for {exchange_id}: {e}")
        return None

def process_single_spread(spdid, instrumentname):
    result = {}
    
    # Read spread data from shared memory
    spread_data = read_from_shm(spdid)
    if not spread_data:
        return {"error": f"SPID {spdid} not found in shared memory."}

    ltp = spread_data.get("Touchline", {}).get("LastTradedPrice")
    if ltp is None or not isinstance(ltp, (int, float)):
        return {"error": f"Invalid or missing LTP for SPID {spdid}"}

    result['LTP'] = ltp
    if(ltp==0):
        print(spread_data)
    #print(instrumentname.get(str(spdid), "Unknown Instrument"),ltp)
    result['instrument_name'] = instrumentname.get(str(spdid), "Unknown Instrument")  # Fixed key lookup

    a1 = 0
    b1 = 0

    if spdid in spd:
        result['related_spids'] = []
        related_spids = spd[spdid]
        for i, related_spid in enumerate(related_spids):
            related_data = {'spid': related_spid, 'instrument_name': instrumentname.get(str(related_spid), "Unknown Instrument")}  # Fixed key lookup
            related_spread_data = read_from_shm(related_spid)
            
            if related_spread_data:
                bids = related_spread_data.get("Bids", [])
                asks = related_spread_data.get("Asks", [])
                
                if ltp > 0:
                    if i == 0 and asks:
                        a1 = asks[0].get("Price", 0)
                        related_data['ask_price'] = a1
                    elif i == 1 and bids:
                        b1 = bids[0].get("Price", 0)
                        related_data['bid_price'] = b1
                else:
                    if i == 0 and bids:
                        b1 = bids[0].get("Price", 0)
                        related_data['bid_price'] = b1
                    elif i == 1 and asks:
                        a1 = asks[0].get("Price", 0)
                        related_data['ask_price'] = a1
            else:
                related_data['error'] = 'Data not found in shared memory.'
                return None

            result['related_spids'].append(related_data)

        actual_spread = abs(b1 - a1)
        total_profit = actual_spread * 175  # Assuming contract size is 175

        result['spread'] = actual_spread
        result['profit'] = total_profit
        result['expiry_dates'] = [date.strftime("%Y-%m-%d") for date in EXPIRY_DATES]

    return result

def process_spread_data():
    result = {}
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_single_spread, spid, instrumentname): spid for spid in spd}
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

    with open('processed_spread_data.json', 'w') as file:
        json.dump(result, file, indent=4)

    return {'message': 'Data processed and saved successfully'}

@app.route('/process-spread-data', methods=['GET'])
def process_and_store_spread_data():
    response = process_spread_data()
    return jsonify(response)

@app.route('/get-spread-data', methods=['GET'])
def get_spread_data():
    try:
        with open('processed_spread_data.json', 'r') as file:
            data = json.load(file)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'Data file not found. Please process the data first.'})

@app.route('/')
def index():
    return render_template('t4.html')

if __name__ == '__main__':
    app.run(debug=True)
