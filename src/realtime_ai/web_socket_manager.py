import json
import logging
import threading
import websocket  # pip install websocket-client
from realtime_ai.models.realtime_ai_options import RealtimeAIOptions

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Synchronous WebSocket manager for handling connections and communication.
    """
    
    def __init__(self, options : RealtimeAIOptions, service_manager):
        self.options = options
        self.service_manager = service_manager
        self.url = f"wss://api.openai.com/v1/realtime?model={self.options.model}"
        self.headers = [
            f"Authorization: Bearer {self.options.api_key}",
            "OpenAI-Beta: realtime=v1"
        ]

        self.ws = None
        self._receive_thread = None

    def connect(self):
        """
        Establishes a WebSocket connection.
        """
        try:
            logger.info(f"WebSocketManager: Connecting to {self.url}")
            self.ws = websocket.WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                header=self.headers
            )

            self._receive_thread = threading.Thread(target=self.ws.run_forever)
            self._receive_thread.start()
            logger.info("WebSocketManager: WebSocket connection established.")
        except Exception as e:
            logger.error(f"WebSocketManager: Connection error: {e}")

    def disconnect(self):
        """
        Gracefully disconnects the WebSocket connection.
        """
        if self.ws:
            self.ws.close()
            if self._receive_thread:
                self._receive_thread.join()
            logger.info("WebSocketManager: WebSocket closed gracefully.")

    def send(self, message: dict):
        """
        Sends a message over the WebSocket.
        """
        if self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                message_str = json.dumps(message)
                self.ws.send(message_str)
                logger.debug(f"WebSocketManager: Sent message: {message_str}")
            except Exception as e:
                logger.error(f"WebSocketManager: Send failed: {e}")

    def _on_open(self, ws):
        logger.info("WebSocketManager: WebSocket connection opened.")
        self.service_manager.on_connected()

    def _on_message(self, ws, message):
        logger.debug(f"WebSocketManager: Received message: {message}")
        self.service_manager.on_message_received(message)

    def _on_error(self, ws, error):
        logger.error(f"WebSocketManager: WebSocket error: {error}")
        self.service_manager.on_error(error)

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocketManager: WebSocket connection closed: {close_status_code} - {close_msg}")
        self.service_manager.on_disconnected(close_status_code, close_msg)
