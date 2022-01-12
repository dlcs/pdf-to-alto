import json
import os
import traceback
import time

import boto3

from logzero import logger

from app.pdf_processor import extract_alto, generate_guid
from app.signal_handler import SignalHandler

REGION = os.environ.get('AWS_REGION', 'eu-west-1')
INCOMING_QUEUE = os.environ.get('INCOMING_QUEUE')
MONITOR_SLEEP_SECS = float(os.environ.get('MONITOR_SLEEP_SECS', 30))

sqs = boto3.resource('sqs', REGION)
s3 = boto3.client('s3', REGION)


def start_monitoring():
    incoming_queue = sqs.get_queue_by_name(QueueName=INCOMING_QUEUE)

    logger.info(f"starting monitoring queue '{INCOMING_QUEUE}'")

    signal_handler = SignalHandler()

    try:
        while not signal_handler.cancellation_requested():
            message_received = False
            for message in _get_messages_from_queue(incoming_queue):
                if message:
                    message_received = True
                    try:
                        _handle_message(message)
                    except Exception:
                        e = traceback.format_exc()
                        logger.error(f"Error processing message: {e}")
                    else:
                        message_received = False

            if not message_received:
                time.sleep(MONITOR_SLEEP_SECS)
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise e

    logger.info(f"stopped monitoring queue '{INCOMING_QUEUE}'...")


def _get_messages_from_queue(queue):
    return queue.receive_messages(WaitTimeSeconds=20, MaxNumberOfMessages=10)


def _handle_message(received_message):
    message = json.loads(received_message.body)
    message_body = json.loads(message["Message"])
    pdf_location = message_body.get("pdfLocation", "")
    if not pdf_location:
        logger.error("Message does not specify pdf location")
        return False

    pdf_identifier = message_body.get("pdfIdentifier", generate_guid())

    extract_alto(pdf_location, pdf_identifier)

    # raise 'done' notification


if __name__ == "__main__":
    start_monitoring()
