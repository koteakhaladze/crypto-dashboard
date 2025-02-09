import json
import requests
import vectorbt as vbt
import pandas as pd
import numpy as np
import pandas_ta as ta
import datetime as dt
 
URL = 'https://api.binance.com/api/v3/klines'
 
intervals_to_secs = {
    '1m':60,
    '3m':180,
    '5m':300,
    '15m':900,
    '30m':1800,
    '1h':3600,
    '2h':7200,
    '4h':14400,
    '6h':21600,
    '8h':28800,
    '12h':43200,
    '1d':86400,
    '3d':259200,
    '1w':604800,
    '1M':2592000
}
 
def download_kline_data(start: dt.datetime, end:dt.datetime ,ticker:str, interval:str)-> pd.DataFrame:
    start = int(start.timestamp()*1000)
    end = int(end.timestamp()*1000)
    full_data = pd.DataFrame()
     
    while start < end:
        par = {'symbol': ticker, 'interval': interval, 'startTime': str(start), 'endTime': str(end), 'limit':1000}
        d = requests.get(URL, params= par).json()
        data = pd.DataFrame(d)
 
        data.index = [dt.datetime.fromtimestamp(x/1000.0) for x in data.iloc[:,0]]
        data=data.astype(float)
        full_data = pd.concat([full_data,data])
         
        start+=intervals_to_secs[interval]*1000*1000
         
    full_data.columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume','Close_time', 'Qav', 'Num_trades','Taker_base_vol', 'Taker_quote_vol', 'Ignore']
     
    return full_data	
# Get data from Binance
# UT Bot Parameters

def calculate_utbot_signals(pd_data, sensitivity, atr_period):
    # Compute ATR And nLoss variable
    pd_data["xATR"] = ta.atr(pd_data["High"], pd_data["Low"], pd_data["Close"], timeperiod=atr_period)
    pd_data["nLoss"] = sensitivity * pd_data["xATR"]
    
    #Drop all rows that have nan, X first depending on the ATR preiod for the moving average
    pd_data = pd_data.dropna()
    pd_data = pd_data.reset_index()

    # Calculating signals
    # Function to compute ATRTrailingStop
    def xATRTrailingStop_func(close, prev_close, prev_atr, nloss):
        if close > prev_atr and prev_close > prev_atr:
            return max(prev_atr, close - nloss)
        elif close < prev_atr and prev_close < prev_atr:
            return min(prev_atr, close + nloss)
        elif close > prev_atr:
            return close - nloss
        else:
            return close + nloss
    
    # Filling ATRTrailingStop Variable
    pd_data["ATRTrailingStop"] = [0.0] + [np.nan for i in range(len(pd_data) - 1)]
    
    for i in range(1, len(pd_data)):
        pd_data.loc[i, "ATRTrailingStop"] = xATRTrailingStop_func(
            pd_data.loc[i, "Close"],
            pd_data.loc[i - 1, "Close"],
            pd_data.loc[i - 1, "ATRTrailingStop"],
            pd_data.loc[i, "nLoss"],
        )

    ema = vbt.MA.run(pd_data["Close"], 1, short_name='EMA', ewm=True)
    
    pd_data["Above"] = ema.ma_crossed_above(pd_data["ATRTrailingStop"])
    pd_data["Below"] = ema.ma_crossed_below(pd_data["ATRTrailingStop"])
    
    pd_data["Buy"] = (pd_data["Close"] > pd_data["ATRTrailingStop"]) & (pd_data["Above"]==True)
    pd_data["Sell"] = (pd_data["Close"] < pd_data["ATRTrailingStop"]) & (pd_data["Below"]==True)
    return pd_data

