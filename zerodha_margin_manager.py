import requests
from kiteconnect import KiteConnect
#from dotenv import load_dotenv

class ZerodhaTradeManager:
    """
    A class to manage Zerodha trades including trading symbol generation
    and margin calculations.
    """
    
    def __init__(self, api_key="s4pnzfflytntrgmf"):
        """
        Initializes the KiteConnect session and sets the access token.
        """
        self.kite = KiteConnect(api_key)
        self.access_token = self.get_access_token()
        self.kite.set_access_token(self.access_token)

    def get_access_token(self):
        """
        Fetches the access token for Zerodha API.
        """
        try:
            response = requests.get("http://110.172.21.62:5005/token/zerodha")
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception("Failed to fetch access token")
        except Exception as e:
            print(f"Error fetching access token: {e}")
            return None

    def generate_trading_symbol(self, trade): #trade should be dict
        """
        Generates a trading symbol using the trade dictionary.
        Hardcoded expiry to '25FEB'.
        """
        stock = trade.get("stock", "")
        instrument_type = trade.get("instrument_type", "")
        strike_price = int(trade.get("strike_price", 0))  # Convert to integer
        hardcoded_expiry = '25FEB'

        return f"{stock}{hardcoded_expiry}{strike_price}{instrument_type}"

    def get_margin_for_trade(self, trade): #trade should be dict that is a row of tradesheet
        """
        Calculates the margin required for the given trade by calling the Kite margin API.
        """
        trading_symbol = self.generate_trading_symbol(trade)

        # Determine transaction type based on trade status
        transaction_type = 'SELL' if trade.get('status') == 'OPEN' else 'BUY'

        order_params = [{
            "exchange": "NFO",
            "tradingsymbol": trading_symbol,
            "transaction_type": transaction_type,
            "variety": "regular",
            "product": "NRML",
            "order_type": "LIMIT",
            "quantity": trade.get("quantity", 0),
            "price": trade.get("entry_price", 0),
            "trigger_price": 0
        }]

        # Call the margin API
        try:
            margin_response = self.kite.order_margins(order_params)
            print(f"Margin response: {margin_response}")
            # return margin_response.get("total", 0) if margin_response else 0
            if margin_response:
                charges = margin_response.get('charges',0)
                charges_total = charges.get('total',0)
                margin_total = margin_response.get('total',0)
                final_margin_required = margin_total - charges_total
                return final_margin_required
            else:
                return 0

        except Exception as e:
            print(f"Error fetching margin: {e}")
            return 0

"""
Margin response for get margin for trade is [{'type': 'equity', 'tradingsymbol': 'DRREDDY25FEB1090PE', 'exchange': 'NFO', 'span': 50518.75, 'exposure': 26756.406250000007, 'option_premium': 0, 'additional': 0, 'bo': 0, 'cash': 0, 'var': 0, 'pnl': {'realised': 0, 'unrealised': 0}, 'leverage': 1, 'charges': {'transaction_tax': 1.71875, 'transaction_tax_type': 'stt', 'exchange_turnover_charge': 0.610671875, 'sebi_turnover_charge': 0.00171875, 'brokerage': 20, 'stamp_duty': 0, 'gst': {'igst': 3.7102303124999993, 'cgst': 0, 'sgst': 0, 'total': 3.7102303124999993}, 'total': 26.041370937499998}, 'total': 77275.15625}]
Margin used is 77275.15625
"""