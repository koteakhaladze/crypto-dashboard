# # consumers.py
# from channels.generic.websocket import AsyncWebsocketConsumer
# import json
# from dashboard.storage import FileStorage
# from dashboard.binance.binance_hourly_bars_real_time import WebSocketClient
# import asyncio
# import logging

# logger = logging.getLogger(__name__)

# class MarketDataConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         logger.info("WebSocket consumer connecting...")
#         await self.accept()
#         logger.info("WebSocket consumer accepted")
        
#         self.ws_client = WebSocketClient.get_instance()
#         self.ws_client.add_consumer(self)
#         logger.info("Added consumer to WebSocket client")
        
#         try:
#             logger.info("Starting WebSocket client run")
#             await self.ws_client.run()
#         except Exception as e:
#             logger.error(f"Error in WebSocket client run: {str(e)}")

#     async def disconnect(self, close_code):
#         logger.info(f"WebSocket consumer disconnecting with code: {close_code}")
#         self.ws_client.remove_consumer(self)
#         logger.info("Removed consumer from WebSocket client")

#     async def receive(self, text_data):
#         logger.info(f"Received message: {text_data[:100]}...")  # Log first 100 chars
#         try:
#             data = json.loads(text_data)
#             logger.info(f"Message type: {data.get('type')}")
#         except Exception as e:
#             logger.error(f"Error processing received message: {str(e)}")