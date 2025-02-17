from dataEngine import MarketDataVWAP, SymphonyAPI
import threading
import time
from strategy import Brain

stop_event = threading.Event()
def connect_market_data_vwap(market_data_vwap):
        market_data_vwap.connect()


if __name__ == "__main__":
    market_data_vwap = MarketDataVWAP()

    # Create a separate thread for connecting to market data
    connect_thread = threading.Thread(target=connect_market_data_vwap, args=(market_data_vwap,))
    connect_thread.start()
    symphony_api = SymphonyAPI(xt=market_data_vwap.xt, market_data_vwap=market_data_vwap)
    symphony_api.login()


    # formatting to keep only required data
    # getting in a pandas dataframe
    df = symphony_api.get_formatted_masters(symphony_api.get_master_instruments())

    df.to_csv('master_instruments.csv')
    symphony_api.subscribtion_handler(market_data_vwap.stock_data)



    # # runs only at the start for all companies
    # # this is to subscribe to 1505 for all companies
    instruments = symphony_api.get_instruments_by_vwap('ASIANPAINT', 20, 2820)
    
    print(instruments)
    # instruments = market_data_api.form_subscribe_request(instruments)
    # response = market_data_api.subscribe_by_instruments(instruments, 1505)
    # print(response)

    brain = Brain()





    # Now you can perform other operations in the main thread
    try:
     while True:
        # For example, retrieve and print VWAP value every second
        brain.put_stock_data(market_data_vwap.get_stock_data())
        vwap = brain.calculate_vwap()

        # time value
        brain.put_options_ohlc(market_data_vwap.options_ohlc)
        brain.calculate_time_value()
        brain.calculate_premium()
        if vwap is not None:
            pass
            
        time.sleep(1)

    except KeyboardInterrupt:
        # Catches Ctrl + C signal
         print("\nReceived Ctrl + C. Stopping threads...")
        # Signal the worker thread to stop
         stop_event.set()
