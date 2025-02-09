from typing import Callable


class FetcherMarketDataEndpoints:
    @staticmethod
    def fetch_data_with_limit(method: Callable, **kwargs):
        """Limit: Default 500; max 1000."""
        response = method(**kwargs).json()
        return response
