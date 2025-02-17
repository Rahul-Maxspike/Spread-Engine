import json

# read data from json file
with open('datachanging.json', 'r') as file:
    data = json.load(file)
spd={10931994:[42541,41498]}
def decide_trade(data,spdid=10931994):

   
    for ticker, info in data.items():
        
        for record in info:
           # sreadprice=s
            # Instead of finding the best bid/ask by max/min price,
            # we just take the first entry in the list:
            bid = record['Bids'][0]['Price']
            ask = record['Asks'][0]['Price']

            spread = ask - bid

            spreads.append({
                "Ticker": ticker,
                "BidPrice": bid,
                "AskPrice": ask,
                "Spread": spread
            })

    # After collecting all ticker entries,
    # pick the lowest bid and highest ask from those first entries.
    buy_ticker = min(spreads, key=lambda x: x['BidPrice'])
    sell_ticker = max(spreads, key=lambda x: x['AskPrice'])

    decisions['Buy'] = {
        "Ticker": buy_ticker['Ticker'],
        "Price": buy_ticker['BidPrice']
    }
    decisions['Sell'] = {
        "Ticker": sell_ticker['Ticker'],
        "Price": sell_ticker['AskPrice']
    }
    decisions['Spread'] = {
        "Spread": sell_ticker['AskPrice'] - buy_ticker['BidPrice']
    }

    return decisions

# Run the algorithm
decisions = decide_trade(data)
print("Trade Decisions:", decisions)
