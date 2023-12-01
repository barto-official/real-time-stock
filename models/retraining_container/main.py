import os
import logging
from datetime import datetime, timedelta
import requests
from river import time_series
import pandas as pd
import pickle
from azure.storage.blob import BlobServiceClient
import mysql.connector
import time
from sqlalchemy import create_engine
import pymysql

TWELVE_DATA_API_KEY = os.getenv('TWELVE_DATA_API_KEY')
AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_twelvedata(symbol, interval, api_key, start_date=None, end_date=None):
    """
        Fetches time series data from the Twelve Data API for a given symbol and interval using HTTP GET requests.

        :param start_date: The start date for the data retrieval (optional).
        :param end_date: The end date for the data retrieval (optional).
        :return: A pandas DataFrame with the price data (the earliest data last for chronological time-series order),
        and the raw data as a dictionary.
        """
    base_url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": api_key,
        "start_date": start_date,
        "end_date": end_date
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
        data = response.json()
        logger.info("Data fetched at {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        df = pd.DataFrame(data['values'])

        # Data for mysql historical archive
        df_general=df.copy()
        df_general['symbol'] = data['meta']['symbol']
        df_general['type'] = data['meta']['type']
        df_general.rename(columns={'open': 'open_price'}, inplace=True)
        df_general.astype({'open_price': 'float64'})
        df_general['datetime'] = pd.to_datetime(df_general['datetime'])
        df_general.drop(columns=['high', 'low', 'close'], inplace=True)

        df['datetime'] = pd.to_datetime(df['datetime'])
        df.drop(columns=['datetime', 'high', 'low', 'close'], inplace=True)
        return df.iloc[::-1], df_general
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTPError occurred: {e}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException occurred: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise


def train_model(data):
    """
        Trains a HoltWinters time series model on the provided data.
        Takes only one variable because it is a real-time model. Check River documentation for more info.

        :param data: A pandas DataFrame with time series data to train the model.
        :return: The trained model.
        """
    model = time_series.HoltWinters(
        alpha=0.3,
        beta=0.1,
        gamma=0.6,
        seasonality=12,
        multiplicative=True
    )
    try:
        for timestamp, value in data["open"].items():
            numeric_value = float(value)
            model = model.learn_one(numeric_value)
        logger.info("Model trained")
        return model
    except ValueError as e:
        logger.error(f"ValueError in training model: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during model training: {e}")
        raise


def save_and_upload_model(model, connection_string, container_name):
    """
        Saves the trained model locally and then uploads it to Azure Blob Storage.

        :param model: The trained model to be saved and uploaded.
        :param connection_string: Azure Blob Storage connection string.
        :param container_name: The name of the Azure Blob Storage container.
        """
    model_name = f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    try:
        pickle.dump(model, open(model_name, "wb"))
        logger.info("Model saved locally")

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=model_name)
        with open(model_name, "rb") as data:
            blob_client.upload_blob(data, metadata={"model": "holtwinters", "type": "forecasting", 'alpha': "0.3",
                                                    'beta': "0.1", 'gamma': "0.6", 'seasonality': "12",
                                                    'multiplicative': 'True'})
        os.remove(model_name)  # Remove the local file after upload
        logger.info("Model uploaded to Azure Blob Storage and removed locally")
    except Exception as e:
        logger.error(f"An error occurred in saving or uploading the model: {e}")
        raise


def write_data_to_mysql(df):
    """
    Writes data to MySQL in bulk using a DataFrame.

    :param df: DataFrame containing data to be written to the database.
    """
    connection_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    engine = create_engine(connection_string)

    try:
        # Example: Assuming 'datetime' is your unique field
        existing_records = pd.read_sql_query('SELECT datetime FROM raw_data_bitcoin', con=engine)
        unique_df = df[~df['datetime'].isin(existing_records['datetime'])]

        # Now use `to_sql` with 'append' to add only new, unique records
        unique_df.to_sql('raw_data_bitcoin', con=engine, if_exists='append', index=False)

        logger.info("Bulk data written to MySQL")
    except Exception as e:
        logger.error(f"Error during bulk database write: {e}")
        raise


def main():
    logging.info("Starting the script")
    start_time=time.time()
    # Create a connection to MySQL database
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor()
        cursor.execute('''
                    CREATE TABLE IF NOT EXISTS raw_data_bitcoin (
                        datetime DATETIME PRIMARY KEY,
                        symbol VARCHAR(255),
                        type VARCHAR(255),
                        open_price FLOAT
                    )
                ''')

        conn.commit()
        # Check if the table is empty
        cursor.execute("SELECT COUNT(*) FROM raw_data_bitcoin")
        if cursor.fetchone()[0] == 0:
            logging.info("The table is empty.")
            #If the table is empty, fetch data from the last 7 days (max by API)
            data_to_train, data_general = fetch_twelvedata('BTC/USD', '1min', TWELVE_DATA_API_KEY, datetime.now() - timedelta(days=7), datetime.now() - timedelta(seconds=10))
        else:
            # If the table is not empty, fetch only the last 5 hours
            data_to_train, data_general = fetch_twelvedata('BTC/USD', '1min', TWELVE_DATA_API_KEY, datetime.now() - timedelta(hours=5), datetime.now() - timedelta(seconds=10))
        cursor.close()
        conn.close()
        model = train_model(data_to_train)
        save_and_upload_model(model, AZURE_STORAGE_CONNECTION_STRING, 'models')
        write_data_to_mysql(data_general)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise e
    finally:
        logger.info("Script finished at{}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        #print time in minutes
        logger.info("Script took --- %s minutes ---" % ((time.time() - start_time)/60))


if __name__ == "__main__":
    main()


