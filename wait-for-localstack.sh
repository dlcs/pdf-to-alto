#!/bin/bash

# This is a shim to hold up starting the main python app until localstack is ready
# when running in real AWS infra the SQS queues will already exist

pip install awscli
until AWS_ACCESS_KEY_ID=foo AWS_SECRET_ACCESS_KEY=bar aws sqs get-queue-url --queue-name ${INCOMING_QUEUE} --endpoint-url ${LOCALSTACK_ADDRESS} --region ${AWS_REGION}; do
  echo 'waiting for queue..'
  sleep 10
done

python3 /opt/app/monitor.py
