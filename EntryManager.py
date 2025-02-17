import csv
import os

class SpreadEntryManager:
    def __init__(self, csv_file='spread_positions.csv'):
        self.csv_file = csv_file
        # Ensure CSV has a header if not present
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'spread_id',
                    'buy_ticker_id', 'buy_ticker_name', 'buy_quantity', 'buy_entry_price', 'buy_exit_price',
                    'sell_ticker_id', 'sell_ticker_name', 'sell_quantity', 'sell_entry_price', 'sell_exit_price'
                ])

    def _load_positions(self):
        """Load existing positions into a list of dicts."""
        positions = []
        if os.path.exists(self.csv_file):
            with open(self.csv_file, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    positions.append(row)
        return positions

    def _save_positions(self, positions):
        """Save the list of dicts back to the CSV file."""
        with open(self.csv_file, 'w', newline='') as file:
            fieldnames = [
                'spread_id',
                'buy_ticker_id', 'buy_ticker_name', 'buy_quantity', 'buy_entry_price', 'buy_exit_price',
                'sell_ticker_id', 'sell_ticker_name', 'sell_quantity', 'sell_entry_price', 'sell_exit_price'
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(positions)

    def position_exists(self, spread_id):
        positions = self._load_positions()
        for row in positions:
            if row['spread_id'] == str(spread_id):
                return True
        return False

    def create_position(
        self,
        spread_id,
        buy_ticker_id, buy_ticker_name, buy_quantity, buy_entry_price,
        sell_ticker_id, sell_ticker_name, sell_quantity, sell_entry_price
    ):
        """Add a new position to CSV if none exists for this spread_id."""
        if self.position_exists(spread_id):
            print(f"Position for spread_id {spread_id} already exists. Skipping.")
            return

        positions = self._load_positions()
        new_entry = {
            'spread_id': str(spread_id),
            'buy_ticker_id': str(buy_ticker_id),
            'buy_ticker_name': buy_ticker_name,
            'buy_quantity': str(buy_quantity),
            'buy_entry_price': str(buy_entry_price),
            'buy_exit_price': "",
            'sell_ticker_id': str(sell_ticker_id),
            'sell_ticker_name': sell_ticker_name,
            'sell_quantity': str(sell_quantity),
            'sell_entry_price': str(sell_entry_price),
            'sell_exit_price': ""
        }
        positions.append(new_entry)
        self._save_positions(positions)
        print(f"Created new position entry for spread_id {spread_id}.")
