# real-time-stock

## About the Project

This project aims at designing and implement a system to predict the Bitcoin price for the next minute using statistical and machine learning tools. To achieve that, a scalable and elastic architecture to stream data in real-time and minimize latency is proposed. While based on mainly Microsoft Azure components, it can be reimplemented using other cloud providers or open-source projects. The system shows promising results with data fetching in a truly real-time manner using Socket programming (2-3 seconds between consecutive data points) and latency of 2-3 seconds from getting data to prediction. The architecture is based mainly on asynchronous programming mode due to scalability, non-blocking I/O operations like WebSocket communication and data fetching, and handling operations for multiple users concurrently. 

Technologies used:
* Python 10.0
* Azure Components: Azure EventHub (or Azure Eventhub AIO), Azure Function, Azure Instance Container, Container App Jobs
* Docker Containers
* River Library for Machine Learning model and online retraining
* MySQL
* FastAPI (or Flask for synchronous backend)
* TwelveData API 

