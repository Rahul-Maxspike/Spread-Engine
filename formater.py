import json
import csv

# Define the header keys that correspond to each field in your pipe-delimited strings.
keys = [
    "exchange",            # e.g., NSEFO
    "token",               # e.g., 101335
    "instrument_category", # e.g., 2
    "underlying",          # e.g., CONCOR
    "contract_symbol",     # e.g., CONCOR25APR780PE
    "instrument_type",     # e.g., OPTSTK or OPTIDX
    "product",             # e.g., CONCOR-OPTSTK
    "contract_unique_id",  # e.g., 2511400101335
    "price1",              # e.g., 123.9
    "price2",              # e.g., 63.3
    "volume",              # e.g., 30001
    "tick_size",           # e.g., 0.05
    "lot_size",            # e.g., 1000
    "trading_status",      # e.g., 1
    "alternate_id",        # e.g., 1100100004749 or -1
    "underlying_name",     # e.g., CONCOR or a descriptive name like Nifty Bank
    "expiry",              # e.g., 2025-04-24T14:30:00
    "strike",              # e.g., 780
    "option_type",         # e.g., 3 (Call) or 4 (Put)
    "option_description",  # e.g., CONCOR 24APR2025 PE 780
    "flag1",               # e.g., 1
    "flag2",               # e.g., 1
    "contract_code"        # e.g., CONCOR25APR780PE
]

def parse_record(record_str):
    """
    Splits a pipe-delimited string into a list of fields.
    """
    fields = record_str.split("|")
    if len(fields) != len(keys):
        print(f"Warning: Expected {len(keys)} fields but got {len(fields)}. Record: {record_str}")
    return fields

def main():
    # Read the JSON file that contains an array of pipe-delimited strings.
    with open("master_instruments.json", "r") as f:
        data = json.load(f)
    
    # Open the CSV file for writing.
    with open("formateddata.csv", "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Write header row.
        writer.writerow(keys)
        
        # Process and write each record to the CSV.
        for record in data:
            fields = parse_record(record)
            writer.writerow(fields)
    
    print("CSV file 'data.csv' created successfully.")

if __name__ == "__main__":
    main()
