# PDF to ALTO

Service that listens for incoming messages from SQS. On receipt of a message this service will download reference PDF,
extract ALTO file per-page and upload to specified S3 bucket.

If `COMPLETED_TOPIC_ARN` env var specified a notification will be raised.

## Messages Format

The incoming message is in the shape:

```json
{
  "pdfLocation": "https://www.hq.nasa.gov/alsj/a17/A17_FlightPlan.pdf",
  "pdfIdentifier": "a17_flightplan",
  "outputLocation": "s3://pdf-to-alto/a17_flightplan_alto"
}
```

Where
* `pdfLocation` - the URL where PDF can be downloaded from.
* `pdfIdentifier` - unique identifier for PDF.
  where `i` is 0-based page index. If omitted a random uuid will be used.
* `outputLocation` - s3 location where final ALTO files will be output. With or without preceding `s3://` and no
  trailing `/`.

(See [sample.json](/sample.json))

The completed notification message echos back the original message with `"numberOfFiles"` property added.

The generated alto file will be placed in `outputLocation`. The format of each file will depend on value of `PREPEND_ID`
envvar. This format will be (where `i` is the page number):
* If true: `f"{pdfIdentifier}-{i:04d}.xml"`
* else `f"{i:04d}.xml"`,

## Technology

This is a Python script that utilises the following libraries:

* [pdfalto](https://github.com/kermitt2/pdfalto) - C lib used to generate ALTO files.
* [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/) - Python lib used to query PDF object for page dimensions.
* [lxml](https://lxml.de/) - Used to parse ALTO files and update scaled values.
* [requests](https://docs.python-requests.org/en/latest/) - Used to download PDF files.

## Configuration

The following environment variables can be used to configure the app:

| Env Var             | Description                                                          | Default               |
|---------------------|----------------------------------------------------------------------|-----------------------|
| DOWNLOAD_CHUNK_SIZE | Chunk size for downloading PDF                                       | 2048                  |
| WORKING_FOLDER      | Local working folder for storing generated files                     | ./work                |
| REMOVE_WORK_DIR     | Whether to clean up working dir on completion                        | True                  |
| RESCALE_ALTO        | Whether to rescale generated ALTO to page                            | True                  |
| MONITOR_SLEEP_SECS  | How long to sleep long polling operations if no messages received    | 30                    |
| AWS_REGION          | AWS region being used                                                | eu-west-1             |
| INCOMING_QUEUE      | The name of the SQS queue to monitor for incoming messages. Required |                       |
| COMPLETED_TOPIC_ARN | The ARN of a topic to post completion notifications to               |                       |
| LOCALSTACK          | If using LocalStack                                                  | False                 |
| LOCALSTACK_ADDRESS  | Address for LocalStack instance                                      | http://localhost:4566 |

(See [.env.dist](/.env.dist) for sample .env file)

## Running Locally

There is a multi-stage Dockerfile that builds the `pdfalto` binary and copies it to a new stage.

[docker-compose.yml](/docker-compose.yml) will build and start the main Python app alongside a LocalStack instance.

```bash
# build and start image using LocalStack
docker-compose up

# build image
docker build --tag pdf-to-alto:local .

# run docker image and listen to queue
docker run --env-file .env -it --rm --name pdf-to-alto pdf-to-alto:local

# run docker image to process 1 single api
docker run -it --rm --name pdf-to-alto \
  pdf-to-alto:local \
  opt/app/app/pdf_processor.py https://text.example/test.pdf my-pdf-identifier s3://pdf-bucket/alto
```

_Note: Building pdfalto from source takes a few minutes_

### LocalStack

The [`docker-compose.local.yml`](./docker-compose.local.yml) file will spin up a LocalStack instance and configure a few
resource for local testing:

* An S3 bucket titled "pdf-to-alto"
* An SNS topic "incoming-topic" with an SQS subscription to "incoming"
* An SNS topic "completed-topic" with an SQS subscription to "completed"

```bash
docker-compose -f docker-compose.local.yml up
```

To use LocalStack set the `LOCALSTACK` and `LOCALSTACK_ADDRESS` env vars (see above).

When using the aws-cli with LocalStack the `--endpoint-url` needs to be specified. Below are some handy commands to use
when testing:

```bash
# raise sample notification using sample.json
aws --endpoint-url=http://localhost:4566 sns publish --topic-arn arn:aws:sns:eu-west-1:000000000000:incoming-topic --message file://sample.json --region eu-west-1

# clear incoming queue
aws --endpoint-url=http://localhost:4566 sqs purge-queue --queue-url "http://localstack:4566/000000000000/incoming" --region eu-west-1

# check number of 'completed' notifications raised
aws --endpoint-url=http://localhost:4566 sqs get-queue-attributes --queue-url "http://localstack:4566/000000000000/completed" --attribute-names All --region eu-west-1

# check contents of s3
aws --endpoint-url=http://localhost:4566 s3 ls pdf-to-alto --recursive --region eu-west-1
```
