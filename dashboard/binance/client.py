from dataclasses import dataclass

import requests


@dataclass
class Endpoints:
    Kline_Candlestick_Data = '/api/v3/klines'


class Binance:
    def __init__(self):
        self.BASE_URL = 'https://api.binance.com'


class ClientMarketDataEndpoints(Binance):
    def kline_candlestick_data(self, **kwargs):
        response = requests.get(self.BASE_URL + '/' + Endpoints.Kline_Candlestick_Data, params=kwargs)
        return response
