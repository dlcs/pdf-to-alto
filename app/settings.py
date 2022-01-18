import os


def _get_boolean(env_name: str, fallback: str) -> bool:
    return os.environ.get(env_name, fallback).lower() in ("true", "t", "1")


DOWNLOAD_CHUNK_SIZE = int(os.environ.get("DOWNLOAD_CHUNK_SIZE", 2048))
WORKING_FOLDER = os.environ.get("WORKING_FOLDER", "./work")
REMOVE_WORK_DIR = _get_boolean("REMOVE_WORK_DIR", "True")
RESCALE_ALTO = _get_boolean("RESCALE_ALTO", "True")
MONITOR_SLEEP_SECS = float(os.environ.get("MONITOR_SLEEP_SECS", 30))

# AWS
REGION = os.environ.get("AWS_REGION", "eu-west-1")
INCOMING_QUEUE = os.environ.get("INCOMING_QUEUE")
COMPLETED_TOPIC_ARN = os.environ.get("COMPLETED_TOPIC_ARN")

# LocalStack
LOCALSTACK = _get_boolean("LOCALSTACK", "False")
LOCALSTACK_ADDRESS = os.environ.get("LOCALSTACK_ADDRESS", "http://localhost:4566")
