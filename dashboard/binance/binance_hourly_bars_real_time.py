import asyncio
import json
import pandas as pd

from dashboard.common.const import LIST_SYMBOLS

from ..common.logger import Logger
import pandas_ta as ta

from ..binance.client import ClientMarketDataEndpoints
from ..binance.fetcher import FetcherMarketDataEndpoints

logger = Logger(name='binance_hourly_bars_real_time', log_file='binance_hourly_bars_real_time.log').get_logger()


class WebSocketClient:
    def __init__(self, storage, on_message_callback=None):
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.external_callback = on_message_callback
        self.storage = storage
        self.websocket = None
        self.running = False
        self.consumers = set()
        self.ws = None
        self.client = ClientMarketDataEndpoints()
        self.fetcher = FetcherMarketDataEndpoints()


    def add_consumer(self, consumer):
        print("Adding consumer")
        self.consumers.add(consumer)

    def remove_consumer(self, consumer):
        self.consumers.discard(consumer)


    def get_bars(self, **kwargs):
        symbol = kwargs['symbol']

        try:
            data = self.fetcher.fetch_data_with_limit(self.client.kline_candlestick_data, **kwargs)
            if not data:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

            columns = [
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ]

            df = pd.DataFrame(data, columns=columns)
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

            for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['number_of_trades'] = df['number_of_trades'].astype(int)
            df['ticker'] = symbol

            return df
        
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return pd.DataFrame()


    def manage_live_bar(self, data, symbol):
        current_time = pd.Timestamp.now()
        bar_start_time = current_time.floor('h')
        
        historical_df = self.storage.load_hourly_data(symbol)
        if historical_df.empty:
            historical_df = self.get_bars(symbol=symbol, interval='1h', limit=100)
        
        live_bar = pd.DataFrame([{
            'open_time': bar_start_time,
            'close_time': bar_start_time + pd.Timedelta(hours=1),
            'ticker': symbol,
            'open': float(data['o']),
            'high': float(data['h']),
            'low': float(data['l']),
            'close': float(data['c']),
            'volume': float(data['v']),
        }])

        historical_df = historical_df[historical_df['open_time'] < bar_start_time]
        combined_df = pd.concat([historical_df, live_bar])
        
        if current_time.minute == 0 and current_time.second < 10:
            last_complete_bar = self.get_bars(symbol=symbol, interval='1h', limit=1)
            if not last_complete_bar.empty:
                historical_df = pd.concat([historical_df, last_complete_bar])
                self.storage.save_hourly_data(historical_df, symbol)
        
        return combined_df

    async def connect(self):
        try:
            logger.info(f"Attempting to connect to {self.ws_url}")
            self.websocket = await websockets.connect(
                self.ws_url,
                close_timeout=10,
                ping_interval=20,
                ping_timeout=20
            )
            logger.info("Connection successful")
            return True
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"Status code error during connection: {e.status_code}")
            logger.error(f"Response headers: {e.headers if hasattr(e, 'headers') else 'No headers'}")
            return False
        except Exception as e:
            logger.error(f"Connection error: {type(e).__name__}: {str(e)}")
            return False

    async def subscribe(self):
        try:
            params = [f"{symbol.lower()}@kline_1h" for symbol in LIST_SYMBOLS]
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": params,
                "id": 1
            }
            logger.info("Sending subscription message")
            await self.websocket.send(json.dumps(subscribe_message))
            logger.info("Subscription message sent successfully")
        except Exception as e:
            logger.error(f"Subscription error: {type(e).__name__}: {str(e)}")
            raise

    async def receive_messages(self):
        while self.running:
            try:
                message = await self.websocket.recv()
                await self.on_message(message)
            except websockets.exceptions.ConnectionClosed as e:
                logger.error(f"WebSocket connection closed: code={e.code}, reason={e.reason}")
                break
            except Exception as e:
                logger.error(f"Error receiving message: {type(e).__name__}: {str(e)}")
                break
    

    def calculate_indicators(self, df):
        try:
            # Reset index to avoid duplicate issues
            df = df.reset_index(drop=True)
            
            # Sort and group
            df = df.sort_values(['ticker', 'open_time'])
            grouped = df.groupby('ticker')

            # Calculate indicators
            df['SMA_10'] = grouped['close'].transform(lambda x: ta.sma(x, length=10))
            df['SMA_100'] = grouped['close'].transform(lambda x: ta.sma(x, length=100))
            
            # Calculate MACD
            macd_dfs = []
            for name, group in grouped:
                macd = ta.macd(group['close'])
                macd_dfs.append(macd['MACD_12_26_9'])
            df['MACD'] = pd.concat(macd_dfs).reset_index(drop=True)
            
            # Calculate RSI
            df['RSI'] = grouped['close'].transform(lambda x: ta.rsi(x))
            
            # Calculate ADX
            adx_dfs = []
            for name, group in grouped:
                adx = ta.adx(group['high'], group['low'], group['close'])
                adx_dfs.append(adx['ADX_14'])
            df['ADX'] = pd.concat(adx_dfs).reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            logger.error(f"DataFrame shape: {df.shape}")
            logger.error(f"Duplicates in index: {df.index.duplicated().any()}")
            return df
   
    async def on_message(self, message):
        try:
            data = json.loads(message)
            if 'k' in data:
                symbol = data['s']
                kline_data = data['k']
                
                updated_df = self.manage_live_bar(kline_data, symbol)
                indicators_df = self.calculate_indicators(updated_df)
                
                if not indicators_df.empty:
                    latest = indicators_df.iloc[-1]
                    # Update using loc with boolean indexing
                    mask = self.storage.real_time_data['Symbol'] == symbol
                    if mask.any():
                        self.storage.real_time_data.loc[mask, 'Price'] = float(kline_data['c'])
                        self.storage.real_time_data.loc[mask, 'SMA10'] = latest.get('SMA_10')
                        self.storage.real_time_data.loc[mask, 'SMA100'] = latest.get('SMA_100')
                        self.storage.real_time_data.loc[mask, 'MACD'] = latest.get('MACD')
                        self.storage.real_time_data.loc[mask, 'RSI'] = latest.get('RSI')
                        self.storage.real_time_data.loc[mask, 'ADX'] = latest.get('ADX')
                    else:
                        new_row = pd.DataFrame({
                            'Symbol': [symbol],
                            'Price': [float(kline_data['c'])],
                            'Change': [0],
                            'SMA10': [latest.get('SMA_10')],
                            'SMA100': [latest.get('SMA_100')],
                            'MACD': [latest.get('MACD')],
                            'RSI': [latest.get('RSI')],
                            'ADX': [latest.get('ADX')]
                        })
                        self.storage.real_time_data = pd.concat([self.storage.real_time_data, new_row], ignore_index=True)
        except Exception as e:
            logger.error(f"Message processing error: {str(e)}")

    async def run(self):
        if self.running:
            logger.info("WebSocket client already running")
            return
        self.running = True
        retry_count = 0
        max_retries = 3
        retry_delay = 5

        while self.running and retry_count < max_retries:
            try:
                logger.info(f"Connection attempt {retry_count + 1}/{max_retries}")
                if await self.connect():
                    await self.subscribe()
                    await self.receive_messages()
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        delay = retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                        logger.info(f"Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Run error: {type(e).__name__}: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    delay = retry_delay * (2 ** (retry_count - 1))
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)

        if retry_count >= max_retries:
            logger.error("Max retries reached, stopping WebSocket client")

    async def stop(self):
        logger.info("Stopping WebSocket client")
        self.running = False
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket connection closed successfully")
            except Exception as e:
                logger.error(f"Error closing connection: {type(e).__name__}: {str(e)}")