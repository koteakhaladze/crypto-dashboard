# dashboard/background_tasks.py
import asyncio
import threading
import time
from datetime import datetime
import pandas as pd

from dashboard.binance.binance_hourly_bars_real_time import WebSocketClient
from dashboard.common.const import LIST_SYMBOLS
from dashboard.common.logger import Logger

logger = Logger(name='binance_hourly_bars_real_time', log_file='binance_hourly_bars_real_time.log').get_logger()


class BackgroundTasks:
    def __init__(self, storage, fetcher, client):
        self.storage = storage
        self.fetcher = fetcher
        self.client = client
        self.running = False
        self.last_update = time.time()
    
    def update_hourly_data(self):
        while self.running:
            try:
                current_time = time.time()
                current_dt = datetime.fromtimestamp(current_time)
                
                # Check at start of hour
                if current_dt.minute == 0 and current_dt.second < 10:
                    if current_time - self.last_update >= 3600:
                        for symbol in LIST_SYMBOLS:
                            try:
                                last_bar = self.client.get_bars(
                                    symbol=symbol, 
                                    interval='1h', 
                                    limit=1
                                )
                                if not last_bar.empty:
                                    historical_df = self.storage.load_hourly_data(symbol)
                                    if not historical_df.empty:
                                        historical_df = pd.concat([historical_df, last_bar])
                                        self.storage.save_hourly_data(historical_df, symbol)
                            except Exception as e:
                                logger.error(f"Error updating hourly data for {symbol}: {str(e)}")
                        
                        self.last_update = current_time
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in hourly update loop: {str(e)}")
                time.sleep(60)

    def start(self):
        # thread = threading.Thread(
        #     target=self.update_hourly_data,
        #     daemon=True,
        #     name='HourlyDataUpdate'
        # )
        # thread.start()
        # logger.info("Started hourly data update thread")

        if not self.running:
            self.running = True
            
            def run_async_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ws = WebSocketClient(self.storage)
                loop.run_until_complete(ws.run())
            print("Running async loop")
            self.thread = threading.Thread(target=run_async_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False