import constants
import pandas as pd
from datetime import datetime, time as dt_time

class Brain:
    def __init__(self):
        self.stock_data = None
        self.options_ohlc = None
        self.options_ohlc_calculated = None

    def put_stock_data(self, stock_data) :
        self.stock_data = stock_data
    
    def put_options_ohlc(self, options_ohlc):
        self.options_ohlc = options_ohlc

    def calculate_time_value(self):
        try:
            options_ohlc = self.options_ohlc.copy()
            stock_data = self.stock_data.copy()
            if options_ohlc == {} or stock_data == None:
                return None

            for exchange_id, data in options_ohlc.items():
                mapped_data = data.get("mappedData")
                data_1512 = data.get("1512Data")

                # from stock data get the vwap where the mapped_data displayName is same as stock_data displayName
                

                vwap = stock_data.get(mapped_data.get("displayName")).get("Touchline").get("VWAP")
                strike = mapped_data.get("Strike")

                if mapped_data.get('OptionType') == 'CE':
                    intrinsic_value = vwap - strike
                elif mapped_data.get('OptionType') == 'PE':
                    intrinsic_value = strike - vwap
                else:
                    print(f"Invalid Option Type: {mapped_data.get('OptionType')}")
                    continue
                if intrinsic_value < 0:
                    intrinsic_value = 0
                
                time_value = data_1512.get("LastTradedPrice") - intrinsic_value
                
                options_ohlc[exchange_id]['calculatedValues'] = {}

                # putting time_value and intrinsic_value in the options_ohlc
                options_ohlc[exchange_id]['calculatedValues']["timeValue"] = round(time_value, 2)
                options_ohlc[exchange_id]['calculatedValues']["intrinsicValue"] = round(intrinsic_value, 2)
                options_ohlc[exchange_id]['mappedData']["vwap"] = round(vwap, 2)
                options_ohlc[exchange_id]['mappedData']['lotSize'] = stock_data.get(mapped_data.get("displayName")).get("lotSize")
                options_ohlc[exchange_id]['mappedData']['interval'] = stock_data.get(mapped_data.get("displayName")).get("strike")
                options_ohlc[exchange_id]['mappedData']['underlyingLTP'] = stock_data.get(mapped_data.get("displayName")).get("Touchline").get("LastTradedPrice")

            self.options_ohlc_calculated = options_ohlc
        except Exception as e:
            print(f"Error in calculate_time_value: {e}")

    def calculate_premium(self):
        try:
            if self.options_ohlc_calculated == {} or self.options_ohlc_calculated == None:
                return None
            
            flattened_data = [
                {**{"ID": key}, **{inner_key: inner_value for sub_dict in value.values() for inner_key, inner_value in sub_dict.items()}}
                for key, value in self.options_ohlc_calculated .items()
            ]

            # Convert to DataFrame
            df = pd.DataFrame(flattened_data)

            # drop columns
            # ID,MessageCode,MessageVersion,ApplicationType,TokenID,ExchangeSegment,BookType,XMarketType
            # df = df.drop(columns=['ID', 'MessageCode', 'MessageVersion', 'ApplicationType', 'TokenID', 'ExchangeSegment', 'BookType', 'XMarketType'])

            df['totalThetaAvailable'] = round(df['timeValue'].astype(float) * df['lotSize'].astype(float), 2)

            df = df.sort_values(by=['totalThetaAvailable'], ascending=[False])
            # reset index
            df = df.reset_index(drop=True)

            # if time is greater than 15:00:20 and less than 15:00:30
            # then save the premium.csv
            if datetime.now().time() > dt_time(15, 0, 00) and datetime.now().time() < dt_time(15, 0, 30):
                df.to_csv("premiumAt3.csv")






            df.to_csv("premium.csv")
        except Exception as e:
            print(f"Error in calculate_premium: {e}")
    

    def calculate_vwap(self):
        if self.stock_data is None:
            return None

        total_vwap = 0
        # loop to calculate individual VWAP values
        for company, data in self.stock_data.items():
            touchline = data.get("Touchline")
            total_vwap += touchline.get("VWAP")
            # print(f"{company} VWAP: {touchline.get('VWAP')}")
            # if company == "Reliance Industries":
            #     print(f"{company} VWAP: {touchline.get('VWAP')}")
        return total_vwap

    def run(self):
        self.strategy.run()