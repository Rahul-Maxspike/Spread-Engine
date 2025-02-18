"""
    Connect.py

    API wrapper for XTS Connect REST APIs.

    :copyright:
    :license: see LICENSE for details.
"""
import configparser
import json
import logging

import requests
from six.moves.urllib.parse import urljoin

import Exception as ex  # Your custom exception module

log = logging.getLogger(__name__)


class XTSCommon:
    """
    Base variables class
    """

    def __init__(self, token=None, userID=None, isInvestorClient=None):
        """Initialize the common variables."""
        self.token = token
        self.userID = userID
        self.isInvestorClient = isInvestorClient


class XTSConnect(XTSCommon):
    """
    The XTS Connect API wrapper class.
    In production, you may initialise a single instance of this class per `api_key`.
    """
    """Get the configurations from config.ini"""
    cfg = configparser.ConfigParser()
    cfg.read('./config.ini')

    # Default root API endpoint. It's possible to
    # override this by passing the `root` parameter during initialisation.
    _default_root_uri = cfg.get('root_url', 'root')
    _default_login_uri = _default_root_uri + "/user/session"
    _default_timeout = 7  # In seconds

    # SSL Flag
    _ssl_flag = cfg.get('SSL', 'disable_ssl')

    # Constants
    # Products
    PRODUCT_MIS = "MIS"
    PRODUCT_NRML = "NRML"

    # Order types
    ORDER_TYPE_MARKET = "MARKET"
    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_STOPMARKET = "STOPMARKET"
    ORDER_TYPE_STOPLIMIT = "STOPLIMIT"

    # Transaction type
    TRANSACTION_TYPE_BUY = "BUY"
    TRANSACTION_TYPE_SELL = "SELL"

    # Squareoff mode
    SQUAREOFF_DAYWISE = "DayWise"
    SQUAREOFF_NETWISE = "Netwise"

    # Squareoff position quantity types
    SQUAREOFFQUANTITY_EXACTQUANTITY = "ExactQty"
    SQUAREOFFQUANTITY_PERCENTAGE = "Percentage"

    # Validity
    VALIDITY_DAY = "DAY"

    # Exchange Segments
    EXCHANGE_NSECM = "NSECM"
    EXCHANGE_NSEFO = "NSEFO"
    EXCHANGE_NSECD = "NSECD"
    EXCHANGE_MCXFO = "MCXFO"
    EXCHANGE_BSECM = "BSECM"

    # URIs to various calls
    _routes = {
        # Interactive API endpoints
        "interactive.prefix": "interactive",
        "user.login": "/interactive/user/session",
        "user.logout": "/interactive/user/session",
        "user.profile": "/interactive/user/profile",
        "user.balance": "/interactive/user/balance",

        "orders": "/interactive/orders",
        "trades": "/interactive/orders/trades",
        "order.status": "/interactive/orders",
        "order.place": "/interactive/orders",
        "bracketorder.place": "/interactive/orders/bracket",
        "bracketorder.modify": "/interactive/orders/bracket",
        "bracketorder.cancel": "/interactive/orders/bracket",
        "order.place.cover": "/interactive/orders/cover",
        "order.exit.cover": "/interactive/orders/cover",
        "order.modify": "/interactive/orders",
        "order.cancel": "/interactive/orders",
        "order.cancelall": "/interactive/orders/cancelall",
        "order.history": "/interactive/orders",

        "portfolio.positions": "/interactive/portfolio/positions",
        "portfolio.holdings": "/interactive/portfolio/holdings",
        "portfolio.positions.convert": "/interactive/portfolio/positions/convert",
        "portfolio.squareoff": "/interactive/portfolio/squareoff",
        "portfolio.dealerpositions": "interactive/portfolio/dealerpositions",
        "order.dealer.status": "/interactive/orders/dealerorderbook",
        "dealer.trades": "/interactive/orders/dealertradebook",

        # Market API endpoints
        "marketdata.prefix": "apimarketdata",
        "market.login": "/apimarketdata/auth/login",
        "market.logout": "/apimarketdata/auth/logout",

        "market.config": "/apimarketdata/config/clientConfig",

        "market.instruments.master": "/apimarketdata/instruments/master",
        "market.instruments.subscription": "/apimarketdata/instruments/subscription",
        "market.instruments.unsubscription": "/apimarketdata/instruments/subscription",
        "market.instruments.ohlc": "/apimarketdata/instruments/ohlc",
        "market.instruments.indexlist": "/apimarketdata/instruments/indexlist",
        "market.instruments.quotes": "/apimarketdata/instruments/quotes",

        "market.search.instrumentsbyid": '/apimarketdata/search/instrumentsbyid',
        "market.search.instrumentsbystring": '/apimarketdata/search/instruments',

        "market.instruments.instrument.series": "/apimarketdata/instruments/instrument/series",
        "market.instruments.instrument.equitysymbol": "/apimarketdata/instruments/instrument/symbol",
        "market.instruments.instrument.futuresymbol": "/apimarketdata/instruments/instrument/futureSymbol",
        "market.instruments.instrument.optionsymbol": "/apimarketdata/instruments/instrument/optionsymbol",
        "market.instruments.instrument.optiontype": "/apimarketdata/instruments/instrument/optionType",
        "market.instruments.instrument.expirydate": "/apimarketdata/instruments/instrument/expiryDate"
    }

    def __init__(self,
                 apiKey,
                 secretKey,
                 source,
                 root=None,
                 debug=False,
                 timeout=None,
                 pool=None,
                 disable_ssl=_ssl_flag):
        """
        Initialise a new XTS Connect client instance.
        """
        self.debug = debug
        self.apiKey = apiKey
        self.secretKey = secretKey
        self.source = source
        self.disable_ssl = disable_ssl
        self.root = root or self._default_root_uri
        self.timeout = timeout or self._default_timeout

        super().__init__()

        # Create requests session only if pool exists. Reuse session
        if pool:
            self.reqsession = requests.Session()
            reqadapter = requests.adapters.HTTPAdapter(**pool)
            self.reqsession.mount("https://", reqadapter)
        else:
            self.reqsession = requests

        # disable requests SSL warning
        requests.packages.urllib3.disable_warnings()

    def _set_common_variables(self, access_token, userID, isInvestorClient):
        """Set the `access_token` received after a successful authentication."""
        super().__init__(access_token, userID, isInvestorClient)

    def _login_url(self):
        """Get the remote login url to which a user should be redirected to initiate the login flow."""
        return self._default_login_uri

    ########################################################################################################
    # Interactive API
    ########################################################################################################

    def interactive_login(self):
        response = None
        try:
            params = {
                "appKey": self.apiKey,
                "secretKey": self.secretKey,
                "source": self.source
            }
            response = self._post("user.login", params)

            if "token" in response['result']:
                self._set_common_variables(
                    response['result']['token'],
                    response['result']['userID'],
                    response['result']['isInvestorClient']
                )
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_order_book(self, clientID=None):
        response = None
        try:
            params = {}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get("order.status", params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_dealer_orderbook(self, clientID=None):
        response = None
        try:
            params = {}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get("order.dealer.status", params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def place_order(self,
                    exchangeSegment,
                    exchangeInstrumentID,
                    productType,
                    orderType,
                    orderSide,
                    timeInForce,
                    disclosedQuantity,
                    orderQuantity,
                    limitPrice,
                    stopPrice,
                    orderUniqueIdentifier,
                    clientID=None):
        response = None
        try:
            params = {
                "exchangeSegment": exchangeSegment,
                "exchangeInstrumentID": exchangeInstrumentID,
                "productType": productType,
                "orderType": orderType,
                "orderSide": orderSide,
                "timeInForce": timeInForce,
                "disclosedQuantity": disclosedQuantity,
                "orderQuantity": orderQuantity,
                "limitPrice": limitPrice,
                "stopPrice": stopPrice,
                "orderUniqueIdentifier": orderUniqueIdentifier
            }

            if not self.isInvestorClient:
                params['clientID'] = clientID

            response = self._post('order.place', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def place_bracketorder(self,
                           exchangeSegment,
                           exchangeInstrumentID,
                           orderType,
                           orderSide,
                           disclosedQuantity,
                           orderQuantity,
                           limitPrice,
                           squarOff,
                           stopLossPrice,
                           trailingStoploss,
                           isProOrder,
                           orderUniqueIdentifier):
        response = None
        try:
            params = {
                "exchangeSegment": exchangeSegment,
                "exchangeInstrumentID": exchangeInstrumentID,
                "orderType": orderType,
                "orderSide": orderSide,
                "disclosedQuantity": disclosedQuantity,
                "orderQuantity": orderQuantity,
                "limitPrice": limitPrice,
                "squarOff": squarOff,
                "stopLossPrice": stopLossPrice,
                "trailingStoploss": trailingStoploss,
                "isProOrder": isProOrder,
                "orderUniqueIdentifier": orderUniqueIdentifier
            }
            response = self._post('bracketorder.place', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_profile(self, clientID=None):
        response = None
        try:
            params = {}
            if not self.isInvestorClient:
                params['clientID'] = clientID

            response = self._get('user.profile', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_balance(self, clientID=None):
        response = None
        if self.isInvestorClient:
            try:
                params = {}
                if not self.isInvestorClient:
                    params['clientID'] = clientID
                response = self._get('user.balance', params)
                return response
            except Exception as e:
                if response and "description" in response:
                    return response['description']
                return str(e)
        else:
            print("Balance: Only available for retail API users.")
            return None

    def modify_order(self,
                     appOrderID,
                     modifiedProductType,
                     modifiedOrderType,
                     modifiedOrderQuantity,
                     modifiedDisclosedQuantity,
                     modifiedLimitPrice,
                     modifiedStopPrice,
                     modifiedTimeInForce,
                     orderUniqueIdentifier,
                     clientID=None):
        response = None
        try:
            appOrderID = int(appOrderID)
            params = {
                'appOrderID': appOrderID,
                'modifiedProductType': modifiedProductType,
                'modifiedOrderType': modifiedOrderType,
                'modifiedOrderQuantity': modifiedOrderQuantity,
                'modifiedDisclosedQuantity': modifiedDisclosedQuantity,
                'modifiedLimitPrice': modifiedLimitPrice,
                'modifiedStopPrice': modifiedStopPrice,
                'modifiedTimeInForce': modifiedTimeInForce,
                'orderUniqueIdentifier': orderUniqueIdentifier
            }

            if not self.isInvestorClient:
                params['clientID'] = clientID

            response = self._put('order.modify', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_trade(self, clientID=None):
        response = None
        try:
            params = {}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get('trades', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_dealer_tradebook(self, clientID=None):
        response = None
        try:
            params = {}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get('dealer.trades', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_holding(self, clientID=None):
        response = None
        try:
            params = {}
            if not self.isInvestorClient:
                params['clientID'] = clientID

            response = self._get('portfolio.holdings', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def bracketorder_cancel(self, appOrderID, clientID=None):
        response = None
        try:
            params = {'boEntryOrderId': int(appOrderID)}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._delete('bracketorder.cancel', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_dealerposition_netwise(self, clientID=None):
        response = None
        try:
            params = {'dayOrNet': 'NetWise'}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get('portfolio.dealerpositions', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_dealerposition_daywise(self, clientID=None):
        response = None
        try:
            params = {'dayOrNet': 'DayWise'}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get('portfolio.dealerpositions', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_position_daywise(self, clientID=None):
        response = None
        try:
            params = {'dayOrNet': 'DayWise'}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get('portfolio.positions', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_position_netwise(self, clientID=None):
        response = None
        try:
            params = {'dayOrNet': 'NetWise'}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get('portfolio.positions', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def convert_position(self, exchangeSegment, exchangeInstrumentID, targetQty, isDayWise, oldProductType,
                         newProductType, clientID=None):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'exchangeInstrumentID': exchangeInstrumentID,
                'targetQty': targetQty,
                'isDayWise': isDayWise,
                'oldProductType': oldProductType,
                'newProductType': newProductType
            }
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._put('portfolio.positions.convert', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def cancel_order(self, appOrderID, orderUniqueIdentifier, clientID=None):
        response = None
        try:
            params = {
                'appOrderID': int(appOrderID),
                'orderUniqueIdentifier': orderUniqueIdentifier
            }
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._delete('order.cancel', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def cancelall_order(self, exchangeSegment, exchangeInstrumentID):
        response = None
        try:
            params = {
                "exchangeSegment": exchangeSegment,
                "exchangeInstrumentID": exchangeInstrumentID
            }
            if not self.isInvestorClient:
                params['clientID'] = self.userID
            response = self._post('order.cancelall', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def place_cover_order(self, exchangeSegment, exchangeInstrumentID, orderSide, orderType,
                          orderQuantity, disclosedQuantity, limitPrice, stopPrice,
                          orderUniqueIdentifier, clientID=None):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'exchangeInstrumentID': exchangeInstrumentID,
                'orderSide': orderSide,
                'orderType': orderType,
                'orderQuantity': orderQuantity,
                'disclosedQuantity': disclosedQuantity,
                'limitPrice': limitPrice,
                'stopPrice': stopPrice,
                'orderUniqueIdentifier': orderUniqueIdentifier
            }
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._post('order.place.cover', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def exit_cover_order(self, appOrderID, clientID=None):
        response = None
        try:
            params = {'appOrderID': appOrderID}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._put('order.exit.cover', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def squareoff_position(self, exchangeSegment, exchangeInstrumentID, productType, squareoffMode,
                           positionSquareOffQuantityType, squareOffQtyValue, blockOrderSending, cancelOrders,
                           clientID=None):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'exchangeInstrumentID': exchangeInstrumentID,
                'productType': productType,
                'squareoffMode': squareoffMode,
                'positionSquareOffQuantityType': positionSquareOffQuantityType,
                'squareOffQtyValue': squareOffQtyValue,
                'blockOrderSending': blockOrderSending,
                'cancelOrders': cancelOrders
            }
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._put('portfolio.squareoff', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_order_history(self, appOrderID, clientID=None):
        response = None
        try:
            params = {'appOrderID': appOrderID}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._get('order.history', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def interactive_logout(self, clientID=None):
        response = None
        try:
            params = {}
            if not self.isInvestorClient:
                params['clientID'] = clientID
            response = self._delete('user.logout', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    ########################################################################################################
    # Market data API
    ########################################################################################################

    def marketdata_login(self):
        response = None
        try:
            params = {
                "appKey": self.apiKey,
                "secretKey": self.secretKey,
                "source": self.source
            }
            response = self._post("market.login", params)

            if "token" in response.get('result', {}):
                self._set_common_variables(
                    response['result']['token'],
                    response['result']['userID'],
                    False
                )
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_config(self):
        response = None
        try:
            params = {}
            response = self._get('market.config', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_quote(self, Instruments, xtsMessageCode, publishFormat):
        response = None
        try:
            params = {
                'instruments': Instruments,
                'xtsMessageCode': xtsMessageCode,
                'publishFormat': publishFormat
            }
            response = self._post('market.instruments.quotes', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def send_subscription(self, Instruments, xtsMessageCode):
        """
        Subscribes to instruments with the given xtsMessageCode.
        This was causing UnboundLocalError previously if the request failed.
        """
        response = None
        try:
            params = {
                'instruments': Instruments,
                'xtsMessageCode': xtsMessageCode
            }
            response = self._post('market.instruments.subscription', json.dumps(params))
            return response
        except Exception as e:
            # If you want to handle invalid token specifically, you can do:
            # if isinstance(e, ex.XTSTokenException):
            #     # handle token refresh or re-raise
            if response and "description" in response:
                return response['description']
            return str(e)

    def send_unsubscription(self, Instruments, xtsMessageCode):
        response = None
        try:
            params = {'instruments': Instruments, 'xtsMessageCode': xtsMessageCode}
            response = self._put('market.instruments.unsubscription', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_master(self, exchangeSegmentList):
        response = None
        try:
            params = {"exchangeSegmentList": exchangeSegmentList}
            response = self._post('market.instruments.master', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_ohlc(self, exchangeSegment, exchangeInstrumentID, startTime, endTime, compressionValue):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'exchangeInstrumentID': exchangeInstrumentID,
                'startTime': startTime,
                'endTime': endTime,
                'compressionValue': compressionValue
            }
            response = self._get('market.instruments.ohlc', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_series(self, exchangeSegment):
        response = None
        try:
            params = {'exchangeSegment': exchangeSegment}
            response = self._get('market.instruments.instrument.series', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_equity_symbol(self, exchangeSegment, series, symbol):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'series': series,
                'symbol': symbol
            }
            response = self._get('market.instruments.instrument.equitysymbol', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_expiry_date(self, exchangeSegment, series, symbol):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'series': series,
                'symbol': symbol
            }
            response = self._get('market.instruments.instrument.expirydate', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_future_symbol(self, exchangeSegment, series, symbol, expiryDate):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'series': series,
                'symbol': symbol,
                'expiryDate': expiryDate
            }
            response = self._get('market.instruments.instrument.futuresymbol', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_option_symbol(self, exchangeSegment, series, symbol, expiryDate, optionType, strikePrice):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'series': series,
                'symbol': symbol,
                'expiryDate': expiryDate,
                'optionType': optionType,
                'strikePrice': strikePrice
            }
            response = self._get('market.instruments.instrument.optionsymbol', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_option_type(self, exchangeSegment, series, symbol, expiryDate):
        response = None
        try:
            params = {
                'exchangeSegment': exchangeSegment,
                'series': series,
                'symbol': symbol,
                'expiryDate': expiryDate
            }
            response = self._get('market.instruments.instrument.optiontype', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def get_index_list(self, exchangeSegment):
        response = None
        try:
            params = {'exchangeSegment': exchangeSegment}
            response = self._get('market.instruments.indexlist', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def search_by_instrumentid(self, Instruments):
        response = None
        try:
            params = {'source': self.source, 'instruments': Instruments}
            response = self._post('market.search.instrumentsbyid', json.dumps(params))
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def search_by_scriptname(self, searchString):
        response = None
        try:
            params = {'searchString': searchString}
            response = self._get('market.search.instrumentsbystring', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    def marketdata_logout(self):
        response = None
        try:
            params = {}
            response = self._delete('market.logout', params)
            return response
        except Exception as e:
            if response and "description" in response:
                return response['description']
            return str(e)

    ########################################################################################################
    # Common Methods
    ########################################################################################################

    def _get(self, route, params=None):
        """Alias for sending a GET request."""
        return self._request(route, "GET", params)

    def _post(self, route, params=None):
        """Alias for sending a POST request."""
        return self._request(route, "POST", params)

    def _put(self, route, params=None):
        """Alias for sending a PUT request."""
        return self._request(route, "PUT", params)

    def _delete(self, route, params=None):
        """Alias for sending a DELETE request."""
        return self._request(route, "DELETE", params)

    def _request(self, route, method, parameters=None):
        """Make an HTTP request."""
        params = parameters if parameters else {}

        # Form a restful URL
        uri = self._routes[route].format(params)
        url = urljoin(self.root, uri)
        headers = {}

        if self.token:
            # set authorization header
            headers.update({'Content-Type': 'application/json', 'Authorization': self.token})

        try:
            r = self.reqsession.request(
                method,
                url,
                data=params if method in ["POST", "PUT"] else None,
                params=params if method in ["GET", "DELETE"] else None,
                headers=headers,
                verify=not self.disable_ssl
            )
        except Exception as e:
            raise e

        if self.debug:
            log.debug("Response: {code} {content}".format(code=r.status_code, content=r.content))

        # Validate the content type.
        if "json" in r.headers.get("content-type", ""):
            try:
                data = json.loads(r.content.decode("utf8"))
            except ValueError:
                raise ex.XTSDataException(
                    "Couldn't parse the JSON response: {content}".format(content=r.content)
                )

            # API error checks
            if data.get("type"):
                # Example: Handle invalid token
                if (r.status_code == 400
                        and data["type"] == "error"
                        and data["description"] == "Invalid Token"):
                    raise ex.XTSTokenException(data["description"])

                if (r.status_code == 400
                        and data["type"] == "error"
                        and data["description"] == "Bad Request"):
                    message = "Description: " + data["description"]
                    # If errors are present in data['result'], you can append them
                    errors = data.get('result', {}).get("errors")
                    if errors:
                        message += " errors: " + str(errors)
                    raise ex.XTSInputException(str(message))

            return data
        else:
            raise ex.XTSDataException(
                "Unknown Content-Type ({content_type}) with response: ({content})".format(
                    content_type=r.headers.get("content-type"),
                    content=r.content
                )
            )
