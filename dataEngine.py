from datetime import datetime
from Connect import XTSConnect
from MarketDataSocketClient import MDSocket_io
import json
import constants
import pandas as pd
from datetime import datetime, time as dt_time
import time

class MarketDataVWAP:
    def __init__(self):
        self.xt = XTSConnect(constants.API_KEY, constants.API_SECRET, constants.SOURCE)
        self.total_value = 0
        self.total_quantity = 0
        self.vwap = None
        self.marketDataToken = None
        self.userID = None
        self.soc = None
        self.stock_data = constants.STOCK_DATA
        self.options_ohlc = {}
        self.mapped_instruments = {}
        # self.SymphonyAPI = SymphonyAPI()
        #self.Instruments = [{'exchangeSegment': 1, 'exchangeInstrumentID': data['exchangeInstrumentID']} for company, data in constants.STOCK_DATA.items()]
        #changing for nsefo 
        self.Instruments = [{'exchangeSegment': 2, 'exchangeInstrumentID': data['exchangeInstrumentID']} for company, data in constants.STOCK_DATA.items()]
        # make a loop that adds this to every company ""touchline": {"tastTradedQunatity": 0}""
        for company, data in self.stock_data.items():
            self.stock_data[company]["Touchline"] = {"LastTradedQunatity": 0, "TotalTradedQuantity": 0, "TotalValue": 0, "VWAP": 0, "subscribed": False}
        # self.Instruments = [{'exchangeSegment': 1, 'exchangeInstrumentID': 2885}]
        self.initialize()
        # self.sql = SQLEgnine()


    def initialize(self):
        response = self.xt.marketdata_login()
        print("Login: ", response)
        self.marketDataToken = response['result']['token']
        self.userID = response['result']['userID']
        self.soc = MDSocket_io(self.marketDataToken, self.userID)
        self.assign_callbacks()

    def on_connect(self):
        print('Market Data Socket connected successfully!')
        print('Sending subscription request for Instruments - \n' + str(self.Instruments))
        response = self.xt.send_subscription(self.Instruments, 1502)
        print('Sent Subscription request!')
        print("Subscription response: ", response)

        #COLOR THIS RESPONSE
        #print("="*50)
       # response = self.xt.send_subscription(self.Instruments, 1505)
       # print('Sent Subscription request!')
       # print("Subscription response: ", response)


    def on_message1512_json_full(self, data):
        try:
            data = json.loads(data)
            exchange_id = data['ExchangeInstrumentID']

            if exchange_id not in self.options_ohlc:
                self.options_ohlc[exchange_id] = {}
            
            
            # Add or update the 1512 data under a specific key in the sub-dictionary
            self.options_ohlc[exchange_id]['1512Data'] = data
            self.options_ohlc[exchange_id]['mappedData'] = self.mapped_instruments[exchange_id]
            
        except Exception as e:
            print(f"Error processing message 1512: {e}")

        
    


    
    def on_message1501_json_full(self, data):
        try:
            data = json.loads(data)
            # check if data has ExchangeInstrumentID and Touchline
            if 'ExchangeInstrumentID' in data and 'Touchline' in data:
                exchange_instrument_id = data['ExchangeInstrumentID']
                data = data['Touchline']
                # only keep LastTradedQunatity, TotalTradedQuantity, Open, High, Low, Close
                data = {key: data[key] for key in ['LastTradedPrice', 'LastTradedQunatity']}
                # only is current time is 15:00
                if datetime.now().time() >= dt_time(9, 0):
                    updated = self.update_stock_data(exchange_instrument_id, data)
                    if updated:
                        # write self.stock_data to json file
                        with open('stock_data.json', 'w') as f:
                            json.dump(self.stock_data, f)
                    else:
                        pass
            else:
                pass
        except Exception as e:
            print(f"Error processing message 1501: {e}")
    
    def on_message1502_json_full(self, data):
        data = json.loads(data)

        # getting best bid and best ask
        # put the data in self.mapped_instruments
        exchange_instrument_id = data['ExchangeInstrumentID']
        if exchange_instrument_id not in self.mapped_instruments:
            self.mapped_instruments[exchange_instrument_id] = {}
        self.mapped_instruments[exchange_instrument_id]['bestBid'] = data['Bids'][0]['Price']
        self.mapped_instruments[exchange_instrument_id]['bestAsk'] = data['Asks'][0]['Price']




    
    # Callback for message code 1505 FULL
    def on_message1505_json_full(self, data):
        # 
        # Sample data:
        # {'MessageCode': 1505, 'MessageVersion': 1, 'ApplicationType': 0, 'TokenID': 0, 'ExchangeSegment': 2, 'ExchangeInstrumentID': 146529, 'BarTime': 1720704239, 'BarVolume': 958500, 'High': 9, 'Low': 9, 'Open': 9, 'Close': 9, 'OpenInterest': 1363500, 'SumOfQtyInToPrice': 0}
        # 
        try:
            data = json.loads(data)
            self.options_ohlc[data['ExchangeInstrumentID']] = data
            # SAVE options_ohlc to json file
            with open('./options_ohlc.json', 'w') as f:
                json.dump(self.options_ohlc, f)


        except Exception as e:
            print(f"Error processing message 1505: {e}")


    def update_stock_data(self, exchangeInstrumentID, new_data):
        try:
            for company, data in self.stock_data.items():
                if data["exchangeInstrumentID"] == exchangeInstrumentID:
                    
                    if self.stock_data[company]["Touchline"]["LastTradedQunatity"] == new_data["LastTradedQunatity"]:
                        return False
                    self.stock_data[company]["Touchline"]["LastTradedQunatity"] = new_data["LastTradedQunatity"]
                    self.stock_data[company]["Touchline"]["LastTradedPrice"] = new_data["LastTradedPrice"]
                    self.stock_data[company]["Touchline"]["TotalTradedQuantity"] += new_data["LastTradedQunatity"]
                    self.stock_data[company]["Touchline"]["TotalValue"] += new_data['LastTradedPrice']  * self.stock_data[company]["Touchline"]["LastTradedQunatity"]
                    self.stock_data[company]["Touchline"]["VWAP"] = (self.stock_data[company]["Touchline"]["TotalValue"] / self.stock_data[company]["Touchline"]["TotalTradedQuantity"])

                    
                    
                    # # check if subscription is done
                    # if not self.stock_data[company]["Touchline"]["subscribed"]:
                    #     instrument_ids = self.SymphonyAPI.get_instruments_by_vwap(constants.STOCK_DATA[company]['displayName'], constants.STOCK_DATA[company]['strike'], self.stock_data[company]["Touchline"]["VWAP"])
                    #     if instrument_ids:
                    #         instruments = self.SymphonyAPI.form_subscribe_request(instrument_ids)
                    #         response = self.SymphonyAPI.subscribe_by_instruments(instruments, 1505)
                    #         if response['type'] == 'success':
                    #             print(f"Subscribed to {company} with instrument ids: {instrument_ids}")
                    #             self.stock_data[company]["Touchline"]["subscribed"] = True
                    #         else:
                    #             pass

                    return True

            return False    
        except Exception as e:
            print(f"Error updating stock data: {e}")
            return False
    
    # for 1512 data
    # this will add the call put data to self.mapped_instruments
    def generate_mapped_instruments(self, df, data_to_add=[]):
        for index, row in df.iterrows():
            exchange_instrument_id = int(row['ExchangeInstrumentID'])
            data = {key: row[key] for key in data_to_add}
            
            # Ensure the main dictionary has a sub-dictionary for master_data
            if exchange_instrument_id not in self.mapped_instruments:
                self.mapped_instruments[exchange_instrument_id] = {}
            
            # Add the data to the master_data sub-dictionary
            self.mapped_instruments[exchange_instrument_id] = data

    def mark_atm_levels(df, current_price):
        """
        Marks ATM levels in the dataframe based on the strike price relative to the ATM strike.
        Args:
            df (pd.DataFrame): Dataframe containing options data.
            current_price (float): The current price of the underlying asset.
        Returns:
            pd.DataFrame: Dataframe with an added 'ATMLevel' column.
        """
        import pandas as pd
        from collections import Counter

        # Ensure 'Strike' is integer type
        #df['Strike'] = df['Strike']
        
        # Get unique strikes and determine the most common interval
        unique_strikes = sorted(df['Strike'].unique())
        intervals = [unique_strikes[i+1] - unique_strikes[i] for i in range(len(unique_strikes)-1)]
        interval = Counter(intervals).most_common(1)[0][0]

        # Calculate the ATM strike
        atm_strike = min(unique_strikes, key=lambda x: abs(x - current_price))

        # Function to compute ATM level for each row
        def compute_atm_level(row):
            strike_diff = (row['Strike'] - atm_strike) // interval
            if row['OptionType'] == 'CE':
                atm_level = f'ATM{strike_diff:+d}'
            elif row['OptionType'] == 'PE':
                atm_level = f'ATM{(-strike_diff):+d}'
            else:
                atm_level = 'OTM'
            return atm_level

        # Apply the function to the dataframe
        df['ATMLevel'] = df.apply(compute_atm_level, axis=1)

        return df
            

            




    def on_disconnect(self):
        print('Market Data Socket disconnected!')

    def assign_callbacks(self):
        self.soc.on_connect = self.on_connect
        self.soc.on_message1512_json_full = self.on_message1512_json_full
        self.soc.on_message1501_json_full = self.on_message1501_json_full
        self.soc.on_message1502_json_full = self.on_message1502_json_full
        self.soc.on_message1505_json_full = self.on_message1505_json_full
        self.soc.on_disconnect = self.on_disconnect

        el = self.soc.get_emitter()
        el.on('connect', self.on_connect)
        el.on('1512-json-full', self.on_message1512_json_full)
        el.on('1501-json-full', self.on_message1501_json_full)
        el.on('1502-json-full', self.on_message1502_json_full)
        el.on('1505-json-full', self.on_message1505_json_full)

    def connect(self):
        self.soc.connect()

    def get_stock_data(self):
        return self.stock_data

#############################################################################

class SymphonyAPI:
    def __init__(self, xt, market_data_vwap):
        self.xt = xt
        self.instruments_master_df = []
        self.stock_data = constants.STOCK_DATA
        self.filtered_master_df = pd.DataFrame()
        self.market_data_vwap = market_data_vwap

    # login to the API
    def login(self):
        response = self.xt.marketdata_login()
        return response

    # get master instruments data from the API, just returns the response
    def get_master_instruments(self, exchangeSegment=['NSEFO',"NSECM"]):
        response = self.xt.get_master(exchangeSegmentList=exchangeSegment)
        
        
  
        return response
    
    # this function will format the master instruments data in a pandas dataframe
    def get_formatted_masters(self, master_instruments):
        response = master_instruments['result'].split('\n')
        #SAVE RESPONSE TO JSON FILE
        with open('./master_instruments.json', 'w') as f:
            json.dump(response, f)
        # split at ,
        response = [x.split(',') for x in response]
        # in each sublist split at |
        response = [[y.split('|') for y in x] for x in response]
        columns = ['ExchangeSegment', 'ExchangeInstrumentID', 'InstrumentType', 'Name', 'Description', 'Series', 'NameWithSeries', 'InstrumentID', 'PriceBand.High', 'PriceBand.Low', 'FreezeQty', 'TickSize', 'LotSize', 'Multiplier', 'Ignore', 'displayName', 'ExpiryDate', 'Strike', 'OptionType', 'TickerName', 'Ignore2', 'Ignore3', 'ticker']
        df = pd.DataFrame([sublist[0] for sublist in response], columns=columns)

       
        # convert ExpiryDate to datetime object
        df['ExpiryDate'] = pd.to_datetime(df['ExpiryDate'])

        # drop Ignore, Ignore2, Ignore3 columns
        df.drop(['Ignore', 'Ignore2', 'Ignore3', 'ticker', 'InstrumentType'], axis=1, inplace=True)
        # drop where 'Series' is not 'OPTSTK'
        df = df[df['Series'] == 'FUTSTK']
        
        # keep only where 'Name' is in stocks's key
        stocks = [company for company in constants.STOCK_DATA.keys()]
        df = df[df['Name'].isin(stocks)]

        df.reset_index(drop=True, inplace=True)
        df.to_csv('master_instruments6.csv')
        self.instruments_master_df = df
        return self.instruments_master_df

    def make_filtered_master_df(self, df):
        # extend the self.filtered_master_df by extending the df
        self.filtered_master_df = pd.concat([self.filtered_master_df, df], ignore_index=True)

    def get_filtered_master_df(self):
        return self.filtered_master_df



    def get_instruments_by_vwap(self, displayName, strike, vwap):
        try:
            # round vwap to nearest strike
            vwap = round(vwap/strike)*strike

            df = self.instruments_master_df
            df = df[(df['displayName'] == displayName)]

            # make a list of 6 strike prices above and below the vwap at interval of strike
            strike_prices = [vwap + i * strike for i in range(-2, 2)]




            # what type is the strike column
            df.loc[:, 'Strike'] = df['Strike'].astype(int)

            # filter the dataframe where strike is in strike_prices
            df = df[df['Strike'].isin(strike_prices)]
            # sort the dataframe by strike
            df.sort_values('Strike', inplace=True)
            

            # Convert ExpiryDate column to datetime format
            df['ExpiryDate'] = pd.to_datetime(df['ExpiryDate'], format='%d/%m/%y %H:%M')

            # Sort by Strike, OptionType and ExpiryDate
            df_sorted = df.sort_values(by=['Strike', 'OptionType', 'ExpiryDate'])

            # Drop duplicates, keeping the first occurrence (closest ExpiryDate)
            df_closest = df_sorted.drop_duplicates(subset=['Strike', 'OptionType'], keep='first')

            # for 'Strike' above vwap, keep only where 'OptionType' is 'CE'
            df_closest_ce = df_closest[(df_closest['Strike'] > vwap) & (df_closest['OptionType'] == 'CE')]


            # for 'Strike' below vwap, keep only where 'OptionType' is 'PE'
            df_closest_pe = pd.concat([df_closest, df_closest[(df_closest['Strike'] < vwap) & (df_closest['OptionType'] == 'PE')]], ignore_index=True)

            df_closest = pd.concat([df_closest_ce, df_closest_pe], ignore_index=True)

            # Reset index
            df_closest = df_closest.reset_index(drop=True)

            # this will add the df_closest to self.filtered_master_df
            self.make_filtered_master_df(df_closest)

            # get a list of ExchangeInstrumentID
            return df_closest['ExchangeInstrumentID'].tolist()
        except Exception as e:
            print(f"{displayName} - Error getting instrument by VWAP: {e}")
            return []
    

    def form_subscribe_request(self, exchangeInstrumentIDs):
        instruments = [{'exchangeSegment': 2, 'exchangeInstrumentID': int(exchangeInstrumentID)} for exchangeInstrumentID in exchangeInstrumentIDs]
        return instruments


    def subscribe_by_instruments(self, exchangeInstruments, messageCode):
        
        response = self.xt.send_subscription(Instruments=exchangeInstruments, xtsMessageCode=messageCode)
        return response

    def subscribtion_handler(self, vwap_data):
        instruments_to_subscribe = []

        for company, data in self.stock_data.items():
            vwap_price = vwap_data[company]['Touchline']['VWAP']
            instruments_to_subscribe.extend(self.get_instruments_by_vwap(company, data['strike'], vwap_price))
        instruments_subsctiption_request_data = self.form_subscribe_request(instruments_to_subscribe)
        self.market_data_vwap.generate_mapped_instruments(self.get_filtered_master_df(), data_to_add=['OptionType', 'displayName', 'Strike'])
        #self.market_data_vwap.mark_atm_levels(self.get_filtered_master_df())

        # send subscription request in parts, max 100 instruments in one request
        # wait for the response to come back before sending the next request
        for i in range(0, len(instruments_subsctiption_request_data), 100):
            response = self.subscribe_by_instruments(instruments_subsctiption_request_data[i:i+100], 1505)
            time.sleep(1)
            print(response)
            response = self.subscribe_by_instruments(instruments_subsctiption_request_data[i:i+100], 1512)
            time.sleep(1)
            print(response)
            response = self.subscribe_by_instruments(instruments_subsctiption_request_data[i:i+100], 1502)
            time.sleep(1)
            print(response)

        # response = self.subscribe_by_instruments(instruments_subsctiption_request_data, 1512)
        # print(response)
        # response = self.subscribe_by_instruments(instruments_subsctiption_request_data, 1502)
        # print(response)


if __name__ == "__main__":
    market_data_api = SymphonyAPI()
    response = market_data_api.login()
    print(response)

    # getting all NSEFO master data
    master = market_data_api.get_master_instruments()

    # formatting to keep only required data
    # getting in a pandas dataframe
    df = market_data_api.get_formatted_masters(master)

    # runs only at the start for all companies
    # this is to subscribe to 1505 for all companies
    instruments = market_data_api.get_instruments_by_vwap('ASIANPAINT', 20, 2820)
    
    print(instruments)
    instruments = market_data_api.form_subscribe_request(instruments)
    response = market_data_api.subscribe_by_instruments(instruments, 1502)
    print(response)