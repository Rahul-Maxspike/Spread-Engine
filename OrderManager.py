import requests

class OrderManager:
    """
    A dedicated class to handle order placement through the ORM API.
    """

    def __init__(self, orm_url="http://110.172.21.62:5004/api/v1/orders/basket"):
        """
        :param orm_url: The endpoint to which the basket order POST request is sent.
        """
        self.orm_url = orm_url

    def placeorder_basket(
        self,
        buy_ticker_id,
        buy_quantity,
        buy_price,
        sell_ticker_id,
        sell_quantity,
        sell_price,
        exchange_segment="NSEFO",    # Change if needed
        order_type="LIMIT",
        order_validity="1",
        client_id="SampleClient",
        strategy_id="MySpreadStrategy"
    ):
        """
        Place a basket order consisting of a BUY leg and a SELL leg.

        :param buy_ticker_id: Instrument ID for the BUY leg
        :param buy_quantity: Quantity to buy
        :param buy_price: Limit price for the BUY order
        :param sell_ticker_id: Instrument ID for the SELL leg
        :param sell_quantity: Quantity to sell
        :param sell_price: Limit price for the SELL order
        :param exchange_segment: e.g., "NSE", "BSE", etc.
        :param order_type: e.g., "LIMIT", "MARKET", etc.
        :param order_validity: e.g., "DAY", "IOC", etc.
        :param client_id: Client ID for the orders
        :param strategy_id: Strategy ID for the orders
        """
        request_payload = {
            "orders": [
                {
                    "exchangeSegment": str(exchange_segment),
                    "exchangeInstrumentId": str(buy_ticker_id),
                    "orderType": "LIMIT",
                    "orderSide": "BUY",
                    "orderValidity": str(order_validity),
                    "quantity": int(buy_quantity),
                    "price": float(buy_price),
                    "clientId": str(client_id),
                    "strategyId": str(strategy_id)
                },
                {
                    "exchangeSegment": str(exchange_segment),
                    "exchangeInstrumentId": str(sell_ticker_id),
                    "orderType": "LIMIT",
                    "orderSide": "SELL",
                    "orderValidity": order_validity,
                    "quantity": int(sell_quantity),
                    "price": float(sell_price),
                    "clientId": str(client_id),
                    "strategyId": str(strategy_id)
                }
            ],
            "clientId": client_id,
            "strategyId": strategy_id
        }

        # Send the POST request
        try:
            response = requests.post(self.orm_url, json=request_payload)
            if response.status_code == 200:
                print("Order placed successfully.")
                # Optionally parse response: data = response.json()
            else:
                print(
                    f"Failed to place order (HTTP {response.status_code}). "
                    f"Response: {response.text}"
                )
        except requests.exceptions.RequestException as e:
            print(f"Error while placing the basket order: {e}")
