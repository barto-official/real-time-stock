import azure.functions as func
import logging
import requests
import time
from time import sleep

app = func.FunctionApp()

@app.function_name(name="Model_retraining")
@app.blob_trigger(arg_name="myblob", path="models/{name}",
                               connection="models") 
async def main(myblob: func.InputStream):
    """
    Function that is triggered when a new blob is uploaded to the models container.
    Calls the API of the models to retrain them. In our case, we have 3 models, so we call the API of each model.

    Parameters
    ----------
    myblob : func.InputStream
        Blob that triggered the function. It contains the name of the blob and other relevant data.
    path : str
        Path of the blob in the container. Check documentation for common patterns.
    connection : str
        Connection string to the container.
    """
    # Log the name and size of the blob
    logging.info(f"Python Blob trigger function processed blob \n"
                 f"Name: {myblob.name}\n"
                 f"Size: {myblob.length} bytes")
    
    # URL of Containers with the models
    api_url = #URL of Model 1
    api_url2 = #URL of Model 2
    api_url3 = #URL of Model 3
    try:
        # Split the blob name to get the filename
        filename = myblob.name.split('/')[-1]

        # Post request to API with the blob name or other relevant data
        response = requests.post(api_url, json={"blob_name": filename})
        
        logging.info(f"API response for Model 1: {response.status_code}, {response.text}")
        time.sleep(180)

        response = requests.post(api_url2, json={"blob_name": filename})
        logging.info(f"API response for Model 2: {response.status_code}, {response.text}")
        time.sleep(180)
        response = requests.post(api_url3, json={"blob_name": filename})
        logging.info(f"API response for Model 3: {response.status_code}, {response.text}")
        logging.info("Function calls completed")
    except Exception as e:
        logging.error(f"API request failed: {e}")
    


