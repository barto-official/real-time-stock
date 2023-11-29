import requests
import pandas as pd
from river import time_series
from datetime import datetime, timedelta
import pickle
import os


""""
#using ytfinance as alternative
def download_historical_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)  # Last 3 years
    data = yf.download('AAPL', start=start_date, end=end_date, interval='1m')
    return data['Close']
"""

def fetch_twelvedata(symbol, interval, api_key, start_date=None, end_date=None):
    base_url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": api_key,
        "start_date": start_date,
        "end_date": end_date
    }
    response = requests.get(base_url, params=params)
    data = response.json()
    df = pd.DataFrame(data['values'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    #df.set_index('datetime', inplace=True)
    df.drop(columns=['datetime', 'high', 'low', 'close', 'volume'], inplace=True)
    print("Data fetched")
    #return reverse df so that the oldest data is first
    return df.iloc[::-1]

def train_model(data, model):
    for timestamp, value in data["open"].items():
        numeric_value = float(value)
        model = model.learn_one(numeric_value)
    print("Model trained")
    return model

def save_model(model, filename='model.pkl'):
    with open(filename, 'wb') as file:
        pickle.dump(model, file)
    print("Model saved")

def load_model(filename='model_initial.pkl'):
    if os.path.exists(filename):
        with open(filename, 'rb') as file:
            print("Model loaded")
            return pickle.load(file)
    else:
        print("Model not found")
        return None

def update_and_predict(model, new_value):
    # Prediction for next 2 minutes (if needed)
    horizon1, horizon2, horizon3, horizon4, horizon5 = model.forecast(horizon=5)
    # Update the model with the new value
    model = model.learn_one(new_value)
    print("Model updated")
    return horizon5, model




