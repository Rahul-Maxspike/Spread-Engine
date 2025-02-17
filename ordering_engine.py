# Library Imports
import pandas as pd
import time
import json
from datetime import datetime, time as dt_time

# Custom Imports
from constants import STOCK_DATA
from logging_setup import CustomLogger, TermLogger
from path_config import IN_MEMORY_TRADE_SHEET_PATH, TRADE_EXECUTION_LOG_PATH, OPTIONS_PREMIUM_PATH, OPTIONS_PREMIUM_AT_3PM_PATH

class OrderingEngine:
    def __init__(self, csv_path, trade_log_path, initial_premium_csv):
        self.logger = CustomLogger("OrderingEngine")
        self.term_logger = TermLogger()
        self.csv_path = csv_path
        self.trade_log_path = trade_log_path
        self.initial_premium = pd.read_csv(initial_premium_csv)
        self.orders = {}  # Store orders with their details
        self.capital = 100000  # 10 lakhs capital
        self.max_quantity = 1000  # Total maximum quantity that can be in active orders
        self.active_orders_quantity = 0  # Total active orders
        self.margin_per_lot = 50000  # Margin per lot
        self.stock_data_constants = STOCK_DATA
        self.trade_sheet = pd.DataFrame({
            'instrumentId': pd.Series(dtype='int'),
            'contract': pd.Series(dtype='str'),
            'sellPrice': pd.Series(dtype='float'),
            'buyPrice': pd.Series(dtype='float'),
            'sellQuantity': pd.Series(dtype='int'),
            'buyQuantity': pd.Series(dtype='int'),
            'totalTradedQuantity': pd.Series(dtype='int'),
            'targetPrice': pd.Series(dtype='float'),
            'quantity': pd.Series(dtype='int')
        })

        self.vwap_range = {}

        # Initialize trade log file
        with open(self.trade_log_path, 'w') as file:
            json.dump([], file)

    def read_csv(self):
        try:
            df =  pd.read_csv(self.csv_path)
            return df
        except Exception as e:
            self.logger.log("error", f"Error in reading CSV: {e}")
            return self.read_csv()

    def square_off(self, instrument_id, exit_price, caller="default"):
        print(f"Squaring off order for instrument {instrument_id} called by {caller}")
        self.term_logger.print_order_details(instrument_id, False, "squareoff", 0, 0, None, None, caller)
        if instrument_id in self.orders:
            order = self.orders[instrument_id]
            order['exit_time'] = datetime.now().isoformat()
            order['buyPrice'] = float(exit_price)
            order['order_type'] = "squareoff"
            self.log_trade(order, "squareoff", caller=caller)
            del self.orders[instrument_id]  # Remove the order after squaring off

    def square_off_all(self):
        for instrument_id in list(self.orders.keys()):
            self.square_off(instrument_id, self.orders[instrument_id]['sellPrice'], caller="Square off all")

    def add_order_to_orders(self, instrument_id, displayName, ltp, sellPrice, buyPrice, target_price, theta, qty_total, strike_price, option_type, order_type, atm_level, adjusted_by_ltp=False):
        """
        Adds a new order to the self.orders dictionary.

        Args:
            instrument_id (int): The instrument ID for the order.
            displayName (str): The display name of the stock.
            ltp (float): Last traded price.
            sellPrice (float): The selling price if the order type is 'sell'.
            buyPrice (float): The buying price if the order type is 'buy'.
            target_price (float): The target price for the order.
            theta (float): The theta value associated with the order.
            qty_total (int): The total quantity for the order.
            strike_price (float): The strike price of the option.
            option_type (str): The type of option ('CE' or 'PE').
            order_type (str): The type of order ('buy', 'sell', 'squareoff').
            atm_level (str): The ATM level of the option.
        """


        if instrument_id in self.orders:
            if order_type == 'sell':
                self.orders[instrument_id]['sellPrice'] = float(((self.orders[instrument_id]['sellPrice'] *
                                                        (self.orders[instrument_id]['qty_total'] - qty_total)) +
                                                        (sellPrice * qty_total)) / self.orders[instrument_id]['qty_total'])
                self.orders[instrument_id]['qty_total'] += qty_total
            elif order_type == 'buy':
                self.orders[instrument_id]['buyPrice'] = float(((self.orders[instrument_id]['buyPrice'] *
                                                        (self.orders[instrument_id]['qty_total'] - qty_total)) +
                                                        (buyPrice * qty_total)) / self.orders[instrument_id]['qty_total'])
                self.orders[instrument_id]['qty_total'] -= qty_total
            elif order_type == 'squareoff':
                self.orders[instrument_id]['buyPrice'] = float(((self.orders[instrument_id]['buyPrice'] *
                                                        (self.orders[instrument_id]['qty_total'] - qty_total)) +
                                                        (buyPrice * qty_total)) / self.orders[instrument_id]['qty_total'])
                self.orders[instrument_id]['qty_total'] = 0
            self.orders[instrument_id]['target_price'] = float(target_price)
            self.orders[instrument_id]['theta'] = float(theta)
            self.orders[instrument_id]['order_time'] = datetime.now().isoformat()
            self.orders[instrument_id]['order_type'] = order_type
            self.orders[instrument_id]['atm_level'] = atm_level
            # if self.orders[instrument_id] not there then make and mark False:
            if 'adjusted_by_ltp' not in self.orders[instrument_id]:
                self.orders[instrument_id]['adjusted_by_ltp'] = False
            else:
                self.orders[instrument_id]['adjusted_by_ltp'] = self.orders[instrument_id]['adjusted_by_ltp']
        else:

            self.orders[instrument_id] = {
                "instrument_id": instrument_id,
                "stock": displayName,
                "ltp": float(ltp),
                "sellPrice": float(sellPrice),
                "buyPrice": float(buyPrice),
                "target_price": float(target_price),
                "theta": float(theta),
                "qty_total": int(qty_total),
                "strike_price": float(strike_price),
                "option_type": option_type,
                "order_time": datetime.now().isoformat(),
                "order_count": 1,
                "order_type": order_type,
                "atm_level": atm_level,
                "adjusted_by_ltp": False
            }

    def add_to_trade_sheet(self, order):
        index = None  # Initialize index to None

        # Check if the instrument already exists in the trade_sheet
        if order['instrument_id'] in self.trade_sheet['instrumentId'].values:
            index = self.trade_sheet[self.trade_sheet['instrumentId'] == order['instrument_id']].index[0]

            # Cast buyPrice and sellPrice to float to ensure compatibility with the column dtype
            self.trade_sheet['buyPrice'] = self.trade_sheet['buyPrice'].astype('float64')
            self.trade_sheet['sellPrice'] = self.trade_sheet['sellPrice'].astype('float64')

            # Handle different order types
            if order['order_type'] == 'sell':
                self.trade_sheet.at[index, 'sellQuantity'] += order['qty_total']
                self.trade_sheet.at[index, 'sellPrice'] = (((self.trade_sheet.at[index, 'sellPrice'] *
                                                            (self.trade_sheet.at[index, 'sellQuantity'] -
                                                            order['qty_total'])) + (order['sellPrice'] * order['qty_total'])) /
                                                            self.trade_sheet.at[index, 'sellQuantity'])
                self.trade_sheet.at[index, 'quantity'] += order['qty_total']
            elif order['order_type'] == 'buy':
                self.trade_sheet.at[index, 'buyQuantity'] += order['qty_total']
                self.trade_sheet.at[index, 'buyPrice'] = (((self.trade_sheet.at[index, 'buyPrice'] *
                                                        (self.trade_sheet.at[index, 'buyQuantity'] -
                                                        order['qty_total'])) + (order['buyPrice'] * order['qty_total'])) /
                                                        self.trade_sheet.at[index, 'buyQuantity'])
                self.trade_sheet.at[index, 'quantity'] -= order['qty_total']
            elif order['order_type'] == 'squareoff':
                self.trade_sheet.at[index, 'buyQuantity'] += order['qty_total']
                self.trade_sheet.at[index, 'buyPrice'] = (((self.trade_sheet.at[index, 'buyPrice'] *
                                                        (self.trade_sheet.at[index, 'buyQuantity'] - order['qty_total'])) +
                                                        (order['buyPrice'] * order['qty_total'])) / self.trade_sheet.at[index, 'buyQuantity'])
                self.trade_sheet.at[index, 'quantity'] = 0
            else:
                self.logger.log('error', f"Invalid order type: {order['order_type']}")

            # Update totalTradedQuantity
            self.trade_sheet.at[index, 'totalTradedQuantity'] = self.trade_sheet.at[index, 'buyQuantity'] + self.trade_sheet.at[index, 'sellQuantity']

        else:
            # Prepare the new trade data
            new_trade = pd.DataFrame([{
                'instrumentId': order['instrument_id'],
                'contract': f"{order['stock']}-{int(order['strike_price'])}-{order['option_type']}",
                'sellPrice': order['sellPrice'] if order['order_type'] == 'sell' else 0,
                'buyPrice': order['buyPrice'] if order['order_type'] in ['buy', 'squareoff'] else 0,
                'sellQuantity': order['qty_total'] if order['order_type'] == 'sell' else 0,
                'buyQuantity': order['qty_total'] if order['order_type'] in ['buy', 'squareoff'] else 0,
                'totalTradedQuantity': order['qty_total'],
                'targetPrice': round(order['target_price'], 2),
                'quantity': 0 if order['order_type'] == 'squareoff' else order['qty_total']
            }])

            # Determine how to concatenate based on whether trade_sheet or new_trade is empty
            if self.trade_sheet.empty and not new_trade.empty:
                self.trade_sheet = new_trade.copy()
                index = self.trade_sheet.index[0]  # Set index to the first (and only) row
            elif not self.trade_sheet.empty and not new_trade.empty:
                # Ensure consistent dtypes before concatenation if both DataFrames are non-empty
                new_trade = new_trade.astype(self.trade_sheet.dtypes)
                self.trade_sheet = pd.concat([self.trade_sheet, new_trade], ignore_index=True)
                index = self.trade_sheet.index[-1]  # Get the index of the newly added row
            elif not self.trade_sheet.empty and new_trade.empty:
                self.logger.warning("Attempted to add an empty or all-NA entry to the trade sheet.")
            else:
                self.logger.warning("Both trade_sheet and new_trade are empty or all-NA.")

        # Ensure quantity is not negative (this could be the case in erroneous buy/sell updates)
        if index is not None and self.trade_sheet.at[index, 'quantity'] < 0:
            # self.logger.log('error', f"Negative quantity detected for instrument {order['instrument_id']}, check order logic.")
            self.trade_sheet.at[index, 'quantity'] = 0

        # Save the trade_sheet to a CSV file
        self.trade_sheet.to_csv(IN_MEMORY_TRADE_SHEET_PATH, index=False)
        # self.term_logger.print_df(self.trade_sheet, "Trade Sheet", "green")

    def get_tradesheet_order_details(self, instrument_id, item):
        # item are the columns of the trade_sheet
        if instrument_id in self.trade_sheet['instrumentId'].values:
            return self.trade_sheet[self.trade_sheet['instrumentId'] == instrument_id][item].values[0]
        else:
            return None

    def check_max_quantity(self, order):
        if order['order_type'] == 'squareoff':
            self.active_orders_quantity -= self.orders[order['instrument_id']]['qty_total']
            return True
        elif order['order_type'] == 'buy':
            self.active_orders_quantity -= order['qty_total']
            return True
        elif order['order_type'] == 'sell':
            if self.active_orders_quantity + order['qty_total'] > self.max_quantity:
                self.logger.warning("Max quantity reached. Not placing the order.")
                return False
            else:
                self.active_orders_quantity += order['qty_total']
                return True

    def log_trade(self, order, order_type, caller):
        self.add_to_trade_sheet(order)
        trade = {
            'timestamp': datetime.now().isoformat(),
            'instrument_id': int(order['instrument_id']),
            'stock': order['stock'],
            'sellPrice': float(order.get('sellPrice', 0)),
            'buyPrice': float(order.get('buyPrice', 0)),
            'target_price': float(order.get('target_price', 0)),
            'qty_total': int(order.get('qty_total', 0)),
            'theta_available_at_entry': float(order['theta']),
            'strike_price': float(order['strike_price']),
            'option_type': order['option_type'],
            'entry_time': order['order_time'],
            'exit_time': order.get('exit_time', None),
            'order_type': order_type,
            'order_count': int(order['order_count']),
            'atm_level': order['atm_level'],
            'caller': caller
        }

        with open(self.trade_log_path, 'r+') as file:
            trades = json.load(file)
            trades.append(trade)
            file.seek(0)
            json.dump(trades, file, indent=4)

    def filter_contracts(self, df):
        df = df[df['totalThetaAvailable'] > 0]
        # is_square_off_due_to_vwap
        # df = df[~df.apply(self._is_square_off_due_to_vwap, axis=1)]
        return df
        # return df[df['ATMLevel'].isin(['ATM+1', 'ATM+2', 'ATM-1', 'ATM-2'])]

    def mark_risk_levels(self, df):
        # Sort the DataFrame based on 'displayName' and 'totalThetaAvailable'
        df = df.sort_values(by=['displayName', 'totalThetaAvailable'], ascending=[True, False])
        
        # Initialize 'risk_level' column with 0
        df['risk_level'] = 0
        
        # Iterate through each unique stock
        for stock in df['displayName'].unique():
            # Create a copy of the DataFrame slice to avoid SettingWithCopyWarning
            stock_df = df[df['displayName'] == stock].copy()
            
            # Generate risk levels for the stock
            risk_levels = list(range(1, len(stock_df) + 1))
            
            # Assign risk levels to 'risk_level' column in the stock_df
            stock_df['risk_level'] = risk_levels[::-1]  # Least risk is 1, highest risk is N
            
            # Update the original DataFrame with the calculated risk levels
            df.loc[df['displayName'] == stock, 'risk_level'] = stock_df['risk_level']
        
        return df


    def mark_vwap_range(self):
        # for the current vwap in initial_premium dataframe we will calculate the range of vwap
        # the range is +- 50% of the strike from STOCK_DATA
        self.term_logger.print_colored("Calculating VWAP range for each stock", "green")
        for displayName in self.initial_premium['displayName'].unique():
            self.term_logger.print_colored(f"Calculating VWAP range for {displayName}", "blue")
            self.term_logger.print_colored(f"Stock data: {self.stock_data_constants.get(displayName)}", "blue")
            stock_df = self.initial_premium[self.initial_premium['displayName'] == displayName].iloc[0]
            interval = self.stock_data_constants.get(displayName)['strike']
            self.vwap_range[displayName] = (stock_df['vwap'] - (0.5 * interval), stock_df['vwap'] + (0.5 * interval))

    def place_order(self, instrument_id, displayName, ltp, bestBid,
                    bestAsk, target_price, theta, qty_total, strike_price,
                    option_type, order_type, atm_level, is_an_add=False, caller="default"):
        self.term_logger.print_order_details(instrument_id, is_an_add, order_type, theta, qty_total, atm_level, option_type, caller)
        instrument_id = int(instrument_id)
        order_time = datetime.now().isoformat()
        entry_price = bestAsk if order_type == "sell" else bestBid
        order_count = self.orders[instrument_id]['order_count'] + 1 if instrument_id in self.orders else 1

        self.orders[instrument_id] = {
            "instrument_id": instrument_id,
            "stock": displayName,
            "ltp": float(ltp),
            "sellPrice": float(entry_price) if order_type == "sell" else 0,
            "buyPrice": float(entry_price) if order_type == "buy" else 0,
            "target_price": float(target_price),
            "theta": float(theta),
            "qty_total": int(qty_total),
            "strike_price": float(strike_price),
            "option_type": option_type,
            "order_time": order_time,
            "order_count": int(order_count),
            "order_type": order_type,
            "atm_level": atm_level
        }
        self.log_trade(self.orders[instrument_id], order_type, caller)
        return True

    def calculate_quantity(self, capital):
        return int(capital / self.margin_per_lot)

    def calculate_balanced_quantity(self, balancer_capital, balancer_theta, balancer_price, order_theta, order_quantity):
        balancer_quantity = int((order_quantity * order_theta) / balancer_theta)
        if balancer_price * balancer_quantity < balancer_capital:
            return balancer_quantity
        else:
            return False

    def _is_square_off_due_to_vwap(self, row):
        vwap = row['vwap']
        vwap_range = self.vwap_range[row['displayName']]
        instrument_id = int(row['ExchangeInstrumentID'])
        if (row['OptionType'] == 'PE' and vwap < vwap_range[0]) or (row['OptionType'] == 'CE' and vwap > vwap_range[1]):
            return True  # Square off the position
        return False  # Do not square off the position

    def _is_square_off_due_to_price_vwap(self, row):
        vwap = row['vwap']
        ltp = row['LastTradedPrice']
        price = row['Strike'] + ltp
        instrument_id = int(row['ExchangeInstrumentID'])
        if (row['OptionType'] == 'PE' and price < vwap) or (row['OptionType'] == 'CE' and price > vwap):
            return True
        return False

    def _get_least_risk_contract(self, stock_df):
        valid_contracts = stock_df[stock_df['totalThetaAvailable'] >= 200]
        if not valid_contracts.empty:
            if not valid_contracts.empty:
                return valid_contracts.loc[valid_contracts['risk_level'].idxmin()]
            else:
                self.logger.log("warning", "No valid contracts available with strike + ltp < vwap")
                return None
        else:
            self.logger.log("warning", "No valid contracts available with totalThetaAvailable > 0")
            return None

    def _get_least_risk_opposite_contract(self, stock_df, least_risk_contract):
        opposite_option_type = 'PE' if least_risk_contract['OptionType'] == 'CE' else 'CE'
        
        valid_contracts = stock_df[stock_df['OptionType'] == opposite_option_type]
        valid_contracts = valid_contracts[valid_contracts['totalThetaAvailable'] > 0]
        # filter contracts for _is_square_off_due_to_price_vwap, keep which are not square off
        valid_contracts = valid_contracts[~valid_contracts.apply(self._is_square_off_due_to_price_vwap, axis=1)]

        # filter the contracts where strike + ltp is less than vwap
        valid_contracts = valid_contracts[valid_contracts['Strike'] + valid_contracts['LastTradedPrice'] < valid_contracts['vwap']]

        
        if valid_contracts.empty:
            self.logger.log("warning", f"No opposite contract with least risk found for {least_risk_contract['displayName']}. Taking any available opposite contract.")
            least_risk_opposite_contract = stock_df[stock_df['OptionType'] == opposite_option_type]
            least_risk_opposite_contract = least_risk_opposite_contract[least_risk_opposite_contract['totalThetaAvailable'] > 0]
            if least_risk_opposite_contract.empty:
                self.logger.log("warning", f"No opposite contract found for {least_risk_contract['displayName']}.")
                return None
            else:
                return least_risk_opposite_contract.loc[least_risk_opposite_contract['risk_level'].idxmin()]

        if not valid_contracts.empty:
            return valid_contracts.loc[valid_contracts['risk_level'].idxmin()]
        else:
            return None

    def place_initial_orders(self, df):
        for displayName in df['displayName'].unique():
            stock_df = df[df['displayName'] == displayName]

            # Find the least risk contract
            least_risk_contract = self._get_least_risk_contract(stock_df)
            if least_risk_contract is None:
                continue

            # Place order in least risk contract
            instrument_id_least = int(least_risk_contract['ExchangeInstrumentID'])
            qty_least = self.calculate_quantity(self.capital * 0.5)
            qty_least = 500

            is_order_placed = self.place_order(
                instrument_id_least, least_risk_contract['displayName'], least_risk_contract['LastTradedPrice'],
                least_risk_contract['bestBid'], least_risk_contract['bestAsk'], least_risk_contract['LastTradedPrice'] * 0.3,
                least_risk_contract['totalThetaAvailable'], qty_least, least_risk_contract['Strike'], least_risk_contract['OptionType'],
                "sell", least_risk_contract['ATMLevel'], False, "Initial order"
            )
            if is_order_placed:
                # Use the new helper function to add the order to self.orders
                self.add_order_to_orders(
                    instrument_id=instrument_id_least,
                    displayName=least_risk_contract['displayName'],
                    ltp=least_risk_contract['LastTradedPrice'],
                    sellPrice=least_risk_contract['bestAsk'],
                    buyPrice=0,
                    target_price=least_risk_contract['LastTradedPrice'] * 0.3,
                    theta=least_risk_contract['totalThetaAvailable'],
                    qty_total=qty_least,
                    strike_price=least_risk_contract['Strike'],
                    option_type=least_risk_contract['OptionType'],
                    order_type="sell",
                    atm_level=least_risk_contract['ATMLevel']
                )

                # Find the least risk contract of the opposite option type
                least_risk_opposite_contract = self._get_least_risk_opposite_contract(stock_df, least_risk_contract)
                if least_risk_opposite_contract is None:
                    continue

                # Place order in least risk opposite option type contract
                instrument_id_least_opposite = int(least_risk_opposite_contract['ExchangeInstrumentID'])
                qty_least_opposite = self.calculate_balanced_quantity(balancer_capital=self.capital * 0.5, balancer_theta=least_risk_opposite_contract['totalThetaAvailable'],
                                                                      balancer_price=least_risk_opposite_contract['bestAsk'], order_theta=least_risk_contract['totalThetaAvailable'],
                                                                      order_quantity=qty_least)
                is_order_placed = self.place_order(
                    instrument_id_least_opposite, least_risk_opposite_contract['displayName'], least_risk_opposite_contract['LastTradedPrice'],
                    least_risk_opposite_contract['bestBid'], least_risk_opposite_contract['bestAsk'], least_risk_opposite_contract['LastTradedPrice'] * 0.3,
                    least_risk_opposite_contract['totalThetaAvailable'], qty_least_opposite, least_risk_opposite_contract['Strike'], least_risk_opposite_contract['OptionType'],
                    "sell", least_risk_opposite_contract['ATMLevel'], False, "Initial order"
                )
                if is_order_placed:
                    # Use the helper function again for the opposite contract
                    self.add_order_to_orders(
                        instrument_id=instrument_id_least_opposite,
                        displayName=least_risk_opposite_contract['displayName'],
                        ltp=least_risk_opposite_contract['LastTradedPrice'],
                        sellPrice=least_risk_opposite_contract['bestAsk'],
                        buyPrice=0,
                        target_price=least_risk_opposite_contract['LastTradedPrice'] * 0.3,
                        theta=least_risk_opposite_contract['totalThetaAvailable'],
                        qty_total=qty_least_opposite,
                        strike_price=least_risk_opposite_contract['Strike'],
                        option_type=least_risk_opposite_contract['OptionType'],
                        order_type="sell",
                        atm_level=least_risk_opposite_contract['ATMLevel']
                    )


    def order_placer_main(self, df):
        df = self.filter_contracts(df)
        df = self.mark_risk_levels(df)
        self.place_initial_orders(df)  # placing the initial orders for least and highest risk contract
        while True:
            df = self.read_csv()  # Continuously read the CSV file
            df = self.filter_contracts(df)
            df = self.mark_risk_levels(df)
            current_time = datetime.now().time()
            # square off all the positions at 3:29 PM
            if current_time >= dt_time(15, 29):
                for instrument_id in list(self.orders.keys()):
                    self.square_off(instrument_id, self.orders[instrument_id]['sellPrice'] * 1.05, caller="Market closing 15:29")
                return

            # keep adjusting the positions
            for displayName in df['displayName'].unique():
                stock_df = df[df['displayName'] == displayName]

                # Check if any adjustments are needed based on the conditions
                self.adjust_positions(stock_df)

            time.sleep(1)

    def adjust_positions(self, df):
        stock = df.iloc[0]['displayName']
        vwap = df.iloc[0]['vwap']
        vwap_range = self.vwap_range[stock]

        if datetime.now().time() >= dt_time(15, 9) and vwap > vwap_range[0] and vwap < vwap_range[1]:  # after 3:09 PM and vwap is in range
            # place in orders in risk level 2 contracts
            for index, row in df.iterrows():
                instrument_id = int(row['ExchangeInstrumentID'])
                if instrument_id in self.orders:
                    continue
                if row['risk_level'] == 2:
                    is_order_placed = self.place_order(
                        instrument_id, row['displayName'], row['LastTradedPrice'], row['bestBid'], row['bestAsk'],
                        row['LastTradedPrice'] * 0.3, row['totalThetaAvailable'], row['lotSize'], row['Strike'], row['OptionType'],
                        "sell", row['ATMLevel'], False, "Adjustment from vwap range"
                    )
                    if is_order_placed:
                        # Use the helper function to add the order to self.orders
                        self.add_order_to_orders(
                            instrument_id=instrument_id,
                            displayName=row['displayName'],
                            ltp=row['LastTradedPrice'],
                            sellPrice=row['bestAsk'],
                            buyPrice=0,
                            target_price=row['LastTradedPrice'] * 0.3,
                            theta=row['totalThetaAvailable'],
                            qty_total=row['lotSize'],
                            strike_price=row['Strike'],
                            option_type=row['OptionType'],
                            order_type="sell",
                            atm_level=row['ATMLevel']
                        )

        for index, row in df.iterrows():
            instrument_id = int(row['ExchangeInstrumentID'])
            theta = row['totalThetaAvailable']
            vwap = row['vwap']
            ltp = row['LastTradedPrice']
            underlying_ltp = row['underlyingLTP']
            try:
                initial_theta = self.initial_premium[self.initial_premium['ExchangeInstrumentID'] == instrument_id]['totalThetaAvailable'].values[0]
                to_pass = False
            except:
                initial_theta = 0
                to_pass = True
            # Adjust based on VWAP and totalThetaAvailable conditions
            if not to_pass:
                if initial_theta.size > 0 and theta >= initial_theta + 20 and to_pass:
                    is_order_placed = self.place_order(
                        instrument_id, row['displayName'], ltp, row['bestBid'], row['bestAsk'],
                        ltp * 0.3, theta, row['lotSize'], row['Strike'], row['OptionType'], "sell", row['ATMLevel'], False, "Adjustment from theta"
                    )
                    if is_order_placed:
                        # Use the helper function to add the order to self.orders
                        self.add_order_to_orders(
                            instrument_id=instrument_id,
                            displayName=row['displayName'],
                            ltp=ltp,
                            sellPrice=row['bestAsk'],
                            buyPrice=0,
                            target_price=ltp * 0.3,
                            theta=theta,
                            qty_total=row['lotSize'],
                            strike_price=row['Strike'],
                            option_type=row['OptionType'],
                            order_type="sell",
                            atm_level=row['ATMLevel']
                        )
                        self.initial_premium.loc[self.initial_premium['ExchangeInstrumentID'] == instrument_id, 'totalThetaAvailable'] = theta

                        # Adjust the opposite contract to match total premium available
                        opposite_option_type = 'PE' if row['OptionType'] == 'CE' else 'CE'
                        opposite_contract = df[(df['OptionType'] == opposite_option_type)]
                        if not opposite_contract.empty:
                            opposite_contract = opposite_contract.loc[opposite_contract['risk_level'].idxmin()]

                        if not opposite_contract.empty:
                            opposite_instrument_id = int(opposite_contract['ExchangeInstrumentID'])
                            qty_opposite = self.calculate_balanced_quantity(balancer_capital=self.capital * 0.5, balancer_theta=opposite_contract['totalThetaAvailable'],
                                                                            balancer_price=opposite_contract['bestAsk'], order_theta=row['totalThetaAvailable'],
                                                                            order_quantity=row['lotSize'])
                            is_order_placed = self.place_order(
                                opposite_instrument_id, opposite_contract['displayName'], opposite_contract['LastTradedPrice'],
                                opposite_contract['bestBid'], opposite_contract['bestAsk'], opposite_contract['LastTradedPrice'] * 0.3,
                                opposite_contract['totalThetaAvailable'], qty_opposite, opposite_contract['Strike'], opposite_contract['OptionType'],
                                "sell", opposite_contract['ATMLevel'], True, "Adjustment from theta"
                            )
                            if is_order_placed:
                                # Use the helper function to add the order to self.orders
                                self.add_order_to_orders(
                                    instrument_id=opposite_instrument_id,
                                    displayName=opposite_contract['displayName'],
                                    ltp=opposite_contract['LastTradedPrice'],
                                    sellPrice=opposite_contract['bestAsk'],
                                    buyPrice=0,
                                    target_price=opposite_contract['LastTradedPrice'] * 0.3,
                                    theta=opposite_contract['totalThetaAvailable'],
                                    qty_total=qty_opposite,
                                    strike_price=opposite_contract['Strike'],
                                    option_type=opposite_contract['OptionType'],
                                    order_type="sell",
                                    atm_level=opposite_contract['ATMLevel']
                                )
                        else:
                            return None
                            self.logger.log("warning", f"No opposite contract found for {row['displayName']}")

            if instrument_id in self.orders:
                initial_theta = self.orders[instrument_id]['theta']
                initial_sell_price = self.orders[instrument_id]['sellPrice']
                is_adjusted_by_ltp = self.orders[instrument_id]['adjusted_by_ltp']

                # if position is already adjusted for then not adjusting again
                if initial_sell_price * 0.7 > ltp and not is_adjusted_by_ltp:
                    higher_strike_contract = df[(df['risk_level'] > row['risk_level']) & (df['OptionType'] == row['OptionType'])]
                    if not higher_strike_contract.empty:
                        # stike should be greater than row strike towards the atm ############################
                        higher_strike_contract = higher_strike_contract.loc[higher_strike_contract['risk_level'].idxmin()]
                        # stike should be greater than row stike
                        is_order_placed = self.place_order(
                            int(higher_strike_contract['ExchangeInstrumentID']), higher_strike_contract['displayName'], higher_strike_contract['LastTradedPrice'],
                            higher_strike_contract['bestBid'], higher_strike_contract['bestAsk'], higher_strike_contract['LastTradedPrice'] * 0.3,
                            higher_strike_contract['totalThetaAvailable'], higher_strike_contract['lotSize'], higher_strike_contract['Strike'],
                            higher_strike_contract['OptionType'], "sell", higher_strike_contract['ATMLevel'], False, "Adjustment from LTP - 1"
                        )
                        if is_order_placed:
                            # Use the helper function to add the order to self.orders
                            self.add_order_to_orders(
                                instrument_id=int(higher_strike_contract['ExchangeInstrumentID']),
                                displayName=higher_strike_contract['displayName'],
                                ltp=higher_strike_contract['LastTradedPrice'],
                                sellPrice=higher_strike_contract['bestAsk'],
                                buyPrice=0,
                                target_price=higher_strike_contract['LastTradedPrice'] * 0.3,
                                theta=higher_strike_contract['totalThetaAvailable'],
                                qty_total=higher_strike_contract['lotSize'],
                                strike_price=higher_strike_contract['Strike'],
                                option_type=higher_strike_contract['OptionType'],
                                order_type="sell",
                                atm_level=higher_strike_contract['ATMLevel']
                            )
                            self.orders[instrument_id]['adjusted_by_ltp'] = True
                    else:
                        self.logger.log("warning", f'''No higher strike contracts found under initial_sell_price * 0.7 for {row['displayName']}
                                        with strike {row['Strike']} and option type {row['OptionType']}''')

                # Square off position if the target price is hit before 3:15 PM
                if datetime.now().time() < dt_time(15, 15):
                    """ADJUSTMENTS FOR VWAP RANGE"""
                    is_price_below_vwap = (row['Strike'] + ltp) < vwap
                    if is_price_below_vwap:
                        if row['OptionType'] == 'PE':
                            self.orders[instrument_id]['target_price'] = self.orders[instrument_id]['sellPrice'] * 0.5
                        elif row['OptionType'] == 'CE':
                            self.square_off(instrument_id, ltp, caller="Target price hit by price < VWAP")
                    else:
                        if row['OptionType'] == 'CE':
                            self.orders[instrument_id]['target_price'] = self.orders[instrument_id]['sellPrice'] * 0.5
                        elif row['OptionType'] == 'PE':
                            self.square_off(instrument_id, ltp, caller="Target price hit by price > VWAP")

                    # """ADJUSTMENT FOR LTP LESS THAN 2 RS"""
                    # if ltp < 2:
                    #     # If ltp is less than 2 rupees, sell the contract closer to VWAP
                    ## if using this then strike+LTP should be closer to vwap, ask rahul if it should be closer in the +ve side or -ve side or just closer in general
                    #     # contract_closer_to_vwap = df[(df['vwap'] < vwap) & (df['OptionType'] == row['OptionType'])]
                    #     contract_closer_to_vwap = df[(df['OptionType'] == row['OptionType'])]
                    #     self.term_logger.print_colored(f"Contract closer to vwap: {contract_closer_to_vwap}", "magenta")
                    #     if not contract_closer_to_vwap.empty:
                    #         contract_closer_to_vwap = contract_closer_to_vwap.iloc[0]
                    #         if int(contract_closer_to_vwap['ExchangeInstrumentID']) not in self.orders:
                    #             is_order_placed = self.place_order(
                    #                 int(contract_closer_to_vwap['ExchangeInstrumentID']), contract_closer_to_vwap['displayName'], contract_closer_to_vwap['LastTradedPrice'],
                    #                 contract_closer_to_vwap['bestBid'], contract_closer_to_vwap['bestAsk'], contract_closer_to_vwap['LastTradedPrice'] * 0.3,
                    #                 contract_closer_to_vwap['totalThetaAvailable'], contract_closer_to_vwap['lotSize'], contract_closer_to_vwap['Strike'],
                    #                 contract_closer_to_vwap['OptionType'], "sell", contract_closer_to_vwap['ATMLevel'], False, "Adjustment from LTP - 2"
                    #             )
                    #             if is_order_placed:
                    #                 # Use the helper function to add the order to self.orders
                    #                 self.add_order_to_orders(
                    #                     instrument_id=int(contract_closer_to_vwap['ExchangeInstrumentID']),
                    #                     displayName=contract_closer_to_vwap['displayName'],
                    #                     ltp=contract_closer_to_vwap['LastTradedPrice'],
                    #                     sellPrice=contract_closer_to_vwap['bestAsk'],
                    #                     buyPrice=0,
                    #                     target_price=contract_closer_to_vwap['LastTradedPrice'] * 0.3,
                    #                     theta=contract_closer_to_vwap['totalThetaAvailable'],
                    #                     qty_total=contract_closer_to_vwap['lotSize'],
                    #                     strike_price=contract_closer_to_vwap['Strike'],
                    #                     option_type=contract_closer_to_vwap['OptionType'],
                    #                     order_type="sell",
                    #                     atm_level=contract_closer_to_vwap['ATMLevel']
                    #                 )

    def run(self):
        while True:
            df = self.read_csv()
            # df = self.filter_contracts(df)
            df = self.mark_risk_levels(df)
            self.mark_vwap_range()
            self.term_logger.print_df(df, "Current Contracts", "cyan")
            self.order_placer_main(df)
            time.sleep(60)  # Adjust the sleep time as needed for the frequency of reading the CSV

# Example usage
engine = OrderingEngine(OPTIONS_PREMIUM_PATH, TRADE_EXECUTION_LOG_PATH, OPTIONS_PREMIUM_AT_3PM_PATH)
engine.run()
