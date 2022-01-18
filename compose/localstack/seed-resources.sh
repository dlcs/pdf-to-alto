#! /bin/bash
# create bucket
awslocal s3 mb s3://pdf-to-alto

# create incoming and complete queue
awslocal sqs create-queue --queue-name incoming
awslocal sqs create-queue --queue-name completed

# create incoming and complete bucket
awslocal sns create-topic --name incoming-topic
awslocal sns create-topic --name completed-topic

# create subscribe sqs queue to respective topic
awslocal sns subscribe --topic-arn arn:aws:sns:eu-west-1:000000000000:incoming-topic --protocol sqs --notification-endpoint arn:aws:sqs:eu-west-1:000000000000:incoming
awslocal sns subscribe --topic-arn arn:aws:sns:eu-west-1:000000000000:completed-topic --protocol sqs --notification-endpoint arn:aws:sqs:eu-west-1:000000000000:completed
