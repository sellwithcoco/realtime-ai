import asyncio
import json
import logging
import websockets
import uuid
from realtime_ai.models.realtime_ai_options import RealtimeAIOptions

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections using asyncio and the websockets library.
    """

    def __init__(self, options: RealtimeAIOptions, service_manager):
        self.options = options
        self.service_manager = service_manager
        self.websocket = None

        if self.options.azure_openai_endpoint:
            self.request_id = uuid.uuid4()
            self.url = self.options.azure_openai_endpoint + f"?api-version={self.options.azure_openai_api_version}" + f"&deployment={self.options.model}"
            self.headers = {
                "x-ms-client-request-id": str(self.request_id),
                "api-key": self.options.api_key,
            }
        else:
            self.url = f"wss://api.openai.com/v1/realtime?model={self.options.model}"
            self.headers = {
                "Authorization": f"Bearer {self.options.api_key}",
                "openai-beta": "realtime=v1",
            }

        self.reconnect_delay = 5 # Time to wait before attempting to reconnect, in seconds

    async def connect(self, reconnection=False):
        """
        Establishes a WebSocket connection.
        """
        try:
            if self.websocket and self.websocket.open:
                logger.info("WebSocketManager: Already connected.")
                return

            logger.info(f"WebSocketManager: Connecting to {self.url}")
            self.websocket = await websockets.connect(self.url, extra_headers=self.headers)
            logger.info("WebSocketManager: WebSocket connection established.")
            await self.service_manager.on_connected(reconnection=reconnection)

            asyncio.create_task(self._receive_messages())  # Begin listening as a separate task
        except Exception as e:
            logger.error(f"WebSocketManager: Connection error: {e}")

    async def _receive_messages(self):
        """
        Listens for incoming WebSocket messages and delegates them to the service manager.
        """
        try:
            async for message in self.websocket:
                await self.service_manager.on_message_received(message)
                logger.debug(f"WebSocketManager: Received message: {message}")
                if "session_expired" in message and "maximum duration of 15 minutes" in message:
                    logger.info("WebSocketManager: Reconnecting due to maximum duration reached.")
                    await asyncio.sleep(self.reconnect_delay)
                    await self.connect(reconnection=True)
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocketManager: Connection closed during receive: {e.code} - {e.reason}")
            await self.service_manager.on_disconnected(e.code, e.reason)
        except asyncio.CancelledError:
            logger.info("WebSocketManager: Receive task was cancelled.")
        except Exception as e:
            logger.error(f"WebSocketManager: Error receiving messages: {e}")

    async def disconnect(self):
        """
        Gracefully disconnects the WebSocket connection.
        """
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocketManager: WebSocket closed gracefully.")
            except Exception as e:
                logger.error(f"WebSocketManager: Error closing WebSocket: {e}")

    async def send(self, message: dict):
        """
        Sends a message over the WebSocket.
        """
        # check if message is cancel_event
        if self.websocket and self.websocket.open:
            try:
                message_str = json.dumps(message)
                await self.websocket.send(message_str)
                logger.debug(f"WebSocketManager: Sent message: {message_str}")
            except Exception as e:
                logger.error(f"WebSocketManager: Send failed: {e}")
                await self.service_manager.on_error(e)
        else:
            logger.error("WebSocketManager: Cannot send message. WebSocket is not connected.")
            raise ConnectionError("WebSocket is not connected.")
