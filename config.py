import os
import logging
import time
import langsmith

from logging.handlers import TimedRotatingFileHandler

def setup_langsmith(llm, dataset="tro-queries"):
    client = langsmith.Client()
    chain_results = client.run_on_dataset(
        dataset_name="tro-queries",
        llm_or_chain_factory=llm,
        project_name="tro-pacific-assistant",
        concurrency_level=5,
        verbose=True,
    )

    return langsmith

def setup_logging():

    LOG_DIR = 'logs/'
    os.makedirs(LOG_DIR, exist_ok=True)  # Ensure log directory exists

    # Define a custom formatter
    class CustomFormatter(logging.Formatter):
        converter = time.gmtime  # Convert time to UTC

        def formatTime(self, record, datefmt=None):
            ct = self.converter(record.created)
            return time.strftime('%Y-%m-%dT%H:%M:%S', ct)

    # Initialize logger with level INFO
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Set up general log handler with rotation by day
    handler_info = TimedRotatingFileHandler(os.path.join(LOG_DIR, 'general.log'), when='midnight', backupCount=7)
    handler_info.setFormatter(CustomFormatter('%(asctime)sZ info: %(message)s'))
    logger.addHandler(handler_info) 

    # Set up info log handler with rotation by day
    handler_info = TimedRotatingFileHandler(os.path.join(LOG_DIR, 'info.log'), when='midnight', backupCount=7)
    handler_info.setLevel(logging.INFO)
    handler_info.setFormatter(CustomFormatter('%(asctime)sZ info: %(message)s'))
    logger.addHandler(handler_info)

    # Set up error log handler with rotation by day
    handler_error = TimedRotatingFileHandler(os.path.join(LOG_DIR, 'error.log'), when='midnight', backupCount=7)
    handler_error.setLevel(logging.ERROR)
    handler_error.setFormatter(CustomFormatter('%(asctime)sZ error: %(message)s'))
    logger.addHandler(handler_error)

    return logger