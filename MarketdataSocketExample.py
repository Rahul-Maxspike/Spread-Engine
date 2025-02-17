from datetime import datetime

from Connect import XTSConnect
from MarketDataSocketClient import MDSocket_io
import json
# MarketData API Credentials
API_KEY = '0b84a5c57dcdf2b3a32261'
API_SECRET = 'Djya854$gm'
SOURCE = 'WebAPI'

# Initialise
xt = XTSConnect(API_KEY, API_SECRET, SOURCE)

# Login for authorization token
response = xt.marketdata_login()
print("Login: ", response)
# Store the token and userid
response = response
set_marketDataToken = response['result']['token']
set_muserID = response['result']['userID']
print("Login: ", response)

# Connecting to Marketdata socket
soc = MDSocket_io(set_marketDataToken, set_muserID)

# Instruments for subscribing


#for instument read instrument_list.json file

with open('Titaninstrument_list.json') as f:
    data = json.load(f)
   
    Instruments = data
#Instruments = [
#                 {'exchangeSegment': 1, 'exchangeInstrumentID': 2885},
                #{'exchangeSegment': 1, 'exchangeInstrumentID': 26000},
#                 {'exchangeSegment': 2, 'exchangeInstrumentID': 42541}
#               ]

# Callback for connection
def on_connect():
    """Connect from the socket."""
    print('Market Data Socket connected successfully!')

    # # Subscribe to instruments
    print('Sending subscription request for Instruments - \n' + str(Instruments))
    response = xt.send_subscription(Instruments, 1502)
    print('Sent Subscription request!')
    print("Subscription response: ", response)

# Callback on receiving message
def on_message(data):
    print('I received a message!')

# Callback for message code 1501 FULL
def on_message1501_json_full(data):
    print('I received a 1501 Touchline message!' + data)

# Callback for message code 1502 FULL
def on_message1502_json_full(data):
    print('I received a 1502 Market depth message!' + data)

# Callback for message code 1505 FULL
def on_message1505_json_full(data):
    print('I received a 1505 Candle data message!' + data)

# Callback for message code 1507 FULL
def on_message1507_json_full(data):
    print('I received a 1507 MarketStatus data message!' + data)

# Callback for message code 1510 FULL
def on_message1510_json_full(data):
    print('I received a 1510 Open interest message!' + data)

# Callback for message code 1512 FULL
def on_message1512_json_full(data):
    #print('I received a 1512 Level1,LTP message!' + data)
    print('xxxxx')
    

# Callback for message code 1105 FULL
# def on_message1105_json_full(data):
    # print('I received a 1105, Instrument Property Change Event message!' + data)


# Callback for message code 1501 PARTIAL
def on_message1501_json_partial(data):
    print('I received a 1501, Touchline Event message!' + data)

# Callback for message code 1502 PARTIAL
def on_message1502_json_partial(data):
    print('I received a 1502 Market depth message!' + data)

# Callback for message code 1505 PARTIAL
def on_message1505_json_partial(data):
    print('I received a 1505 Candle data message!' + data)

# Callback for message code 1510 PARTIAL
def on_message1510_json_partial(data):
    print('I received a 1510 Open interest message!' + data)

# Callback for message code 1512 PARTIAL
def on_message1512_json_partial(data):
    #print('I received a 1512, LTP Event message!' + data)
    # for trade in data:
    #     total_value += trade["LastTradedPrice"] * trade["LastTradedQunatity"]
    #     total_quantity += trade["LastTradedQunatity"]

    #     # Calculate VWAP
    #     vwap = total_value / total_quantity

    # print("VWAP:", vwap)
    pass



# Callback for message code 1105 PARTIAL
def on_message1105_json_partial(data):
    print('I received a 1105, Instrument Property Change Event message!' + data)

# Callback for disconnection
def on_disconnect():
    print('Market Data Socket disconnected!')


# Callback for error
def on_error(data):
    """Error from the socket."""
    print('Market Data Error', data)


# Assign the callbacks.
soc.on_connect = on_connect
soc.on_message = on_message
soc.on_message1502_json_full = on_message1502_json_full
soc.on_message1505_json_full = on_message1505_json_full
#soc.on_message1507_json_full = on_message1507_json_full
#soc.on_message1510_json_full = on_message1510_json_full
#soc.on_message1512_json_full = on_message1512_json_full
# soc.on_message1105_json_full = on_message1105_json_full
soc.on_message1502_json_partial = on_message1502_json_partial
soc.on_message1505_json_partial = on_message1505_json_partial
#soc.on_message1510_json_partial = on_message1510_json_partial
#soc.on_message1501_json_partial = on_message1501_json_partial
#soc.on_message1512_json_partial = on_message1512_json_partial
# soc.on_message1105_json_partial = on_message1105_json_partial
#soc.on_disconnect = on_disconnect
#soc.on_error = on_error


# Event listener
el = soc.get_emitter()
el.on('connect', on_connect)
el.on('1501-json-full', on_message1501_json_full)
el.on('1502-json-full', on_message1502_json_full)
#el.on('1507-json-full', on_message1507_json_full)
#el.on('1512-json-full', on_message1512_json_full)
#el.on('1512-json-partial', on_message1505_json_partial)
# el.on('1105-json-full', on_message1105_json_full)

# Infinite loop on the main thread. Nothing after this will run.
# You have to use the pre-defined callbacks to manage subscriptions.

soc.connect()
'''
":1397650178,"PercentChange":-0.59,"Open":22339.05,"High":22427.45,"Low":22263.55,"Close":22519.4,"TotalValueTraded":null,"BuyBackTotalBuy":0,"BuyBackTotalSell":0,"AskInfo":{"Size":0,"Price":0,"TotalOrders":0,"BuyBackMarketMaker":0},"BidInfo":{"Size":0,"Price":0,"TotalOrders":0,"BuyBackMarketMaker":0}}}
I received a 1501 Touchline message!{"MessageCode":1501,"MessageVersion":4,"ApplicationType":0,"TokenID":0,"ExchangeSegment":1,"ExchangeInstrumentID":26000,"ExchangeTimeStamp":1397650179,"Touchline":{"BidInfo":{"Size":0,"Price":0,"TotalOrders":0,"BuyBackMarketMaker":0},"AskInfo":{"Size":0,"Price":0,"TotalOrders":0,"BuyBackMarketMaker":0},"LastTradedPrice":22386,"LastTradedQunatity":0,"TotalBuyQuantity":0,"TotalSellQuantity":0,"TotalTradedQuantity":0,"AverageTradedPrice":22386,"LastTradedTime":1397650179,"LastUpdateTime":1397650179,"PercentChange":-0.59,"Open":22339.05,"High":22427.45,"Low":22263.55,"Close":22519.4,"TotalValueTraded":null,"BuyBackTotalBuy":0,"BuyBackTotalSell":0},"BookType":1,"XMarketType":1,"SequenceNumber":1353296204670191}
I received a 1501 Touchline message!{"MessageCode":1501,"MessageVersion":4,"ApplicationType":0,"TokenID":0,"ExchangeSegment":1,"ExchangeInstrumentID":26000,"ExchangeTimeStamp":1397650179,"BookType":1,"XMarketType":1,"SequenceNumber":1353296268795003,"Touchline":{"LastTradedPrice":22386,"LastTradedQunatity":0,"TotalBuyQuantity":0,"TotalSellQuantity":0,"TotalTradedQuantity":0,"AverageTradedPrice":22386,"LastTradedTime":1397650179,"LastUpdateTime":1397650179,"PercentChange":-0.59,"Open":22339.05,"High":22427.45,"Low":22263.55,"Close":22519.4,"TotalValueTraded":null,"BuyBackTotalBuy":0,"BuyBackTotalSell":0,"AskInfo":{"Size":0,"Price":0,"TotalOrders":0,"BuyBackMarketMaker"
'''