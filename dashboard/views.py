# dashboard/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from dashboard.background_tasks import BackgroundTasks
from dashboard.common.const import LIST_SYMBOLS
from .storage import FileStorage
from django.contrib.auth.decorators import login_required
from .binance.client import ClientMarketDataEndpoints
from .binance.fetcher import FetcherMarketDataEndpoints
from .binance.handler import HandlerMarketDataEndpoints
import pandas as pd
import datetime as dt
import vectorbt as vbt
from .ubot import download_kline_data, calculate_utbot_signals
import json
import logging

logger = logging.getLogger(__name__)
storage = FileStorage()
client = ClientMarketDataEndpoints()
fetcher = FetcherMarketDataEndpoints()
handler = HandlerMarketDataEndpoints()

background_tasks = BackgroundTasks(storage, fetcher, client)
background_tasks.start()

def calculate_monthly_yearly_pnl(pf, signals_data):
    """Calculate monthly and yearly P&L using signals_data dates"""
    # Get daily returns
    daily_returns = pf.returns()
    
    # Convert millisecond timestamps to datetime
    signals_data['Datetime'] = pd.to_datetime(signals_data['Datetime'], unit='ms')
        
    # Use signals_data datetime for returns index
    daily_returns.index = signals_data['Datetime']
        
    # Now group by year and month
    monthly_pnl = []
    monthly_dates = []
    yearly_pnl = []
    yearly_dates = []
    
    # Process monthly returns
    monthly_grouped = daily_returns.groupby([
        daily_returns.index.year,
        daily_returns.index.month
    ])
    
    for (year, month), returns in monthly_grouped:
        # Calculate compounded monthly return
        month_return = (1 + returns).prod() - 1
        monthly_pnl.append(month_return)
        monthly_dates.append(pd.Timestamp(year=year, month=month, day=1))
        logger.info(f"Processed month {year}-{month}: {month_return}")
    
    # Process yearly returns
    yearly_grouped = daily_returns.groupby(daily_returns.index.year)
    
    for year, returns in yearly_grouped:
        # Calculate compounded yearly return
        year_return = (1 + returns).prod() - 1
        yearly_pnl.append(year_return)
        yearly_dates.append(pd.Timestamp(year=year, month=1, day=1))
        logger.info(f"Processed year {year}: {year_return}")
    
    logger.info(f"Calculated {len(monthly_pnl)} monthly returns and {len(yearly_pnl)} yearly returns")
    
    return monthly_pnl, monthly_dates, yearly_pnl, yearly_dates

# Update the table creation to handle potential empty months
def create_pnl_table(monthly_pnl, monthly_dates, yearly_pnl, yearly_dates, precision=2):
    """Create P&L table similar to PineScript output"""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Create DataFrame for monthly returns
    monthly_data = pd.DataFrame({
        'year': [d.year for d in monthly_dates],
        'month': [d.month for d in monthly_dates],
        'pnl': monthly_pnl
    })
    
    # Create DataFrame for yearly returns
    yearly_data = pd.DataFrame({
        'year': [d.year for d in yearly_dates],
        'pnl': yearly_pnl
    })
    
    # Pivot monthly data
    table_data = monthly_data.pivot(
        index='year',
        columns='month',
        values='pnl'
    )
    
    # Rename columns to month names
    table_data.columns = [months[i-1] for i in table_data.columns]
    
    # Add yearly returns
    table_data['Year'] = yearly_data.set_index('year')['pnl']
    
    # Convert to percentages
    table_data = table_data * 100
    
    # Sort years in descending order
    table_data = table_data.sort_index(ascending=False)
    
    return table_data

# views.py
@require_http_methods(["GET"])
def get_market_data(request):
    try:        
        # Get all current data
        data = storage.real_time_data.to_dict('records')
        
        return JsonResponse({
            'success': True,
            'data': data
        })
    except Exception as e:
        logger.error(f"Error getting market data: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def screener_view(request):
    real_time_data = storage.real_time_data
    context = {
        'real_time_data': real_time_data,
        'symbols': LIST_SYMBOLS
    }
    return render(request, 'dashboard/screener.html', context)

def backtest_view(request):
    context = {
        'symbols': LIST_SYMBOLS,
        'timeframes': ['1d', '4h', '1h'],
        'default_start': dt.datetime(2020, 1, 1),
        'default_end': dt.datetime.now(),
        'default_sensitivity': 1.0,
        'default_atr_period': 10
    }
    return render(request, 'dashboard/backtest.html', context)

@require_http_methods(['POST'])
def run_backtest(request):
    try:
        data = json.loads(list(request.POST.keys())[0])
        start_date = dt.datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = dt.datetime.strptime(data['end_date'], '%Y-%m-%d')
        symbol = data['symbol']
        timeframe = data['timeframe']
        sensitivity = float(data['sensitivity'])
        atr_period = int(data['atr_period'])

        data = download_kline_data(start_date, end_date, symbol, timeframe)
        signals_data = calculate_utbot_signals(data, sensitivity, atr_period)
        
        if signals_data is not None:
            pf = vbt.Portfolio.from_signals(
                signals_data["Close"],
                entries=signals_data["Buy"],
                short_entries=signals_data["Sell"],
                upon_opposite_entry='ReverseReduce',
                freq=timeframe
            )
            
            metrics = pf.stats()
            monthly_pnl, monthly_dates, yearly_pnl, yearly_dates = calculate_monthly_yearly_pnl(pf, signals_data)
            pnl_table = create_pnl_table(monthly_pnl, monthly_dates, yearly_pnl, yearly_dates)
            pnl_table = {col: {str(idx): val 
                         for idx, val in data.items() if not pd.isna(val)}
                   for col, data in pnl_table.items()}

            return JsonResponse({
                'success': True,
                'data': {
                    'signals': signals_data.to_dict('records'),
                    'metrics': metrics.to_dict(),
                    'pnl_table': pnl_table
                }
            })
    except Exception as e:
        logger.error(f"Backtest error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})