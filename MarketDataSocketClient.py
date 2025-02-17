import configparser
import os
import json
import socketio

# Initialize global variables for VWAP calculation
total_value = 0
total_quantity = 0

class MDSocket_io(socketio.Client):
    def __init__(self, token, userID, **kwargs):
        # Initialize Socket.IO client
        self.sid = socketio.Client(logger=False, engineio_logger=False)
        self.eventlistener = self.sid

        # Set up event handlers
        self.sid.on('connect', self.on_connect)
        self.sid.on('1512-json-full', self.on_message1512_json_full)
        self.sid.on('1501-json-full', self.on_message1501_json_full)
        self.sid.on('1502-json-full', self.on_message1502_json_full)
        self.sid.on('1505-json-full', self.on_message1505_json_full)
        self.sid.on('disconnect', self.on_disconnect)

        # Read configuration
        currDirMain = os.getcwd()
        configParser = configparser.ConfigParser()
        configFilePath = os.path.join(currDirMain, './config.ini')
        configParser.read(configFilePath)

        self.port = configParser.get('root_url', 'root')
        self.userID = userID
        self.token = token
        self.broadcastMode = configParser.get('root_url', 'broadcastMode')

        # Construct connection URL
        publishFormat = 'JSON'
        self.connection_url = f'{self.port}/?token={token}&userID={userID}&publishFormat={publishFormat}&broadcastMode={self.broadcastMode}'

    def connect(self, headers={}, transports='websocket', namespaces=None, socketio_path='/apimarketdata/socket.io', verify=False):
        # Connect to the socket
        self.sid.connect(url=self.connection_url, headers=headers, transports=transports, namespaces=namespaces, socketio_path=socketio_path)
        self.sid.wait()

    def on_connect(self):
        print('Market Data Socket connected successfully!')

    def on_message1512_json_full(self, data):
        pass

    def on_message1501_json_full(self, data):
        """On receiving message code 1501 full"""
        print('I received a 1501 Level1,Touchline message!' + data)

    def on_message1502_json_full(self, data):
        """On receiving message code 1502 full"""
        print('I received a 1502 Market depth message!' + data)
    
    def on_message1505_json_full(self, data):
        """On receiving message code 1505 full"""
        print('I received a 1505 Candle data message!' + data)

    def on_disconnect(self):
        print('Market Data Socket disconnected!')

    def on_error(self, data):
        print('Market Data Error', data)

    def get_emitter(self):
        return self.eventlistener
