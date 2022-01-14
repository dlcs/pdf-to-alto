import json
import traceback
import time

from logzero import logger

from app.aws_factory import get_aws_resource, get_aws_client
from app.pdf_processor import PDFProcessor, generate_guid
from app.settings import INCOMING_QUEUE, MONITOR_SLEEP_SECS, COMPLETED_TOPIC_ARN
from app.signal_handler import SignalHandler

sqs = get_aws_resource("sqs")
sns = get_aws_client("sns")


def start_monitoring():
    incoming_queue = sqs.get_queue_by_name(QueueName=INCOMING_QUEUE)

    logger.info(f"starting monitoring queue '{INCOMING_QUEUE}'")

    signal_handler = SignalHandler()

    try:
        while not signal_handler.cancellation_requested():
            message_received = False
            for message in _get_messages_from_queue(incoming_queue):
                if message and not signal_handler.cancellation_requested():
                    message_received = True
                    try:
                        if _handle_message(message):
                            message.delete()
                    except Exception:
                        e = traceback.format_exc()
                        logger.error(f"Error processing message: {e}")
                    else:
                        message_received = False

            if not message_received and not signal_handler.cancellation_requested():
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

    output = message_body.get("outputLocation", "")
    if not output:
        logger.error("Message does not specify output location")
        return False

    pdf_identifier = message_body.get("pdfIdentifier", generate_guid())

    processor = PDFProcessor(pdf_location, pdf_identifier, output)
    success = processor.extract_alto()

    if success:
        logger.info(f"Processing {pdf_location} finished successfully")
        _raise_completed_notification(message_body, len(processor.generated_alto))
    else:
        logger.info(f"Processing {pdf_location} failed")

    return success


def _raise_completed_notification(original_message, number_of_altos):
    if not COMPLETED_TOPIC_ARN:
        logger.info("No topic ARN configured.")
        return

    try:
        original_message["numberOfFiles"] = number_of_altos
        response = sns.publish(
            TopicArn=COMPLETED_TOPIC_ARN,
            Message=json.dumps(original_message)
        )
    except Exception as e:
        logger.error(f"Error raising completed notification. {e}")


if __name__ == "__main__":
    start_monitoring()
