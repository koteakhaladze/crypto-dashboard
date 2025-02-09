import pandas as pd


class HandlerMarketDataEndpoints:
    @staticmethod
    def kline_candlestick_data(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """There is Quote asset volume in this endpoint"""
        df = df.rename(columns={0: 'datetime_open', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume',
                                6: 'datetime_close', 7: 'quote_asset_volume', 8: 'number',
                                9: 'Taker_buy_base_asset_volume', 10: 'Taker_buy_quote_asset_volume',
                                11: 'Unused field'})

        df['ticker'] = ticker
        df['datetime'] = pd.to_datetime(df['datetime_open'], unit='ms')

        df = df[['datetime', 'open', 'high', 'low', 'close', 'volume', 'number', 'ticker']]
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return df
