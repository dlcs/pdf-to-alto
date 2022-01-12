# PDF to ALTO

Service that listens for incoming messages from SQS.

On receipt of a message this service will download reference PDF, extract ALTO file per-page and upload to specified S3 bucket.

## Running Locally

There is a multi-stage Dockerfile that builds the [pdfalto](https://github.com/kermitt2/pdfalto) library and copies it to a new stage.

```build
docker build --tag pdf-to-alto:local .

docker run -it --rm --name pdf-to-alto pdf-to-alto:local
```