import os
import pandas as pd
from datetime import datetime
from collections import deque

class FileStorage:
    def __init__(self, data_dir="hourly_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.price_history = {symbol: deque(maxlen=200) for symbol in self.get_symbols()}
        self.real_time_data = pd.DataFrame(columns=['Symbol', 'Price', 'Change', 'SMA10', 'SMA100', 'MACD', 'RSI', 'ADX'])
        self.real_time_prices = {}
        self.price_changes = {}
        self.hourly_data = self.get_hourly_bars()
        self.indicators = {symbol: {} for symbol in self.get_symbols()}

    def get_symbols(self):
        from .binance.binance_hourly_bars_real_time import LIST_SYMBOLS
        return LIST_SYMBOLS

    def save_hourly_data(self, df, symbol):
        file_path = os.path.join(self.data_dir, f"{symbol}_hourly.csv")
        df = df.sort_values('open_time').drop_duplicates(subset=['open_time'], keep='last').tail(100)
        df.to_csv(file_path, index=False)

    def load_hourly_data(self, symbol):
        file_path = os.path.join(self.data_dir, f"{symbol}_hourly.csv")
        if os.path.exists(file_path):
            try:
                return pd.read_csv(file_path, parse_dates=['open_time', 'close_time'])
            except Exception as e:
                print(f"ERROR {symbol}")
                return pd.DataFrame()
        return pd.DataFrame()

    def get_hourly_bars(self, from_time=None):
        dfs = []
        for symbol in self.get_symbols():
            df = self.load_hourly_data(symbol)
            if not df.empty:
                dfs.append(df)
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    def update_price_history(self, symbol, price):
        self.price_history[symbol].append(price)
        
    def update_real_time_data(self, symbol, data):
        mask = self.real_time_data['Symbol'] == symbol
        if mask.any():
            index = mask.idxmax()
            old_price = self.real_time_data.loc[index, 'Price']
            new_price = float(data['c'])
            change = new_price - old_price
            self.real_time_data.loc[index, 'Price'] = new_price
            self.real_time_data.loc[index, 'Change'] = change
        else:
            new_row = pd.DataFrame({
                'Symbol': [symbol], 
                'Price': [float(data['c'])], 
                'Change': [0],
                'SMA10': [None], 
                'SMA100': [None], 
                'MACD': [None], 
                'RSI': [None], 
                'ADX': [None]
            })
            self.real_time_data = pd.concat([self.real_time_data, new_row], ignore_index=True)

    def save_backtest_result(self, result, symbol):
        backtest_dir = os.path.join(self.data_dir, "backtest_results")
        os.makedirs(backtest_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(backtest_dir, f"{symbol}_{timestamp}.csv")
        result.to_csv(file_path, index=False)