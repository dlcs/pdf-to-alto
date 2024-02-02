#! /bin/bash
# create bucket
awslocal s3 mb s3://pdf-to-alto --region eu-west-1

# create incoming and complete queue
awslocal sqs create-queue --queue-name incoming --region eu-west-1
awslocal sqs create-queue --queue-name completed --region eu-west-1

# create incoming and complete bucket
awslocal sns create-topic --name incoming-topic --region eu-west-1
awslocal sns create-topic --name completed-topic --region eu-west-1

# create subscribe sqs queue to respective topic
awslocal sns subscribe --topic-arn arn:aws:sns:eu-west-1:000000000000:incoming-topic --protocol sqs --notification-endpoint arn:aws:sqs:eu-west-1:000000000000:incoming --region eu-west-1
awslocal sns subscribe --topic-arn arn:aws:sns:eu-west-1:000000000000:completed-topic --protocol sqs --notification-endpoint arn:aws:sqs:eu-west-1:000000000000:completed --region eu-west-1
