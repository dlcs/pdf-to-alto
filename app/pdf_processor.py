import os
import subprocess
import sys
import uuid

import requests

from subprocess import PIPE
from logzero import logger
from pathlib import Path
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import resolve1

WORKING_FOLDER = os.environ.get('WORKING_FOLDER', './work')
REMOVE_WORK_DIR = os.environ.get('REMOVE_WORK_DIR', 'True').lower() in ('true', 't', '1')


def extract_alto(pdf_location, pdf_identifier):
    logger.info(f"Processing {pdf_location} with id {pdf_identifier}")
    work_folder = _create_work_folder(pdf_identifier)

    target_file = Path(work_folder, f"{pdf_identifier}.pdf")
    downloaded_pdf = _download_pdf(pdf_location, target_file)

    if not downloaded_pdf:
        logger.error("Unable to download PDF")
        return False

    _generate_alto(target_file, work_folder)

    if REMOVE_WORK_DIR:
        _rm_tree(work_folder)


def generate_guid():
    return str(uuid.uuid4())


def _create_work_folder(pdf_identifier):
    work_folder = Path(WORKING_FOLDER, pdf_identifier, generate_guid())
    work_folder.mkdir(parents=True, exist_ok=False)
    return work_folder


def _download_pdf(pdf_location, target_file):
    try:
        download_request = requests.get(pdf_location, stream=True)
        with open(target_file, 'wb') as file:
            for chunk in download_request.iter_content(2048):
                file.write(chunk)
            # file.write(download_request.content)
        return True
    except Exception as download_exception:
        logger.exception(f"problem during download of {pdf_location} to {target_file}: {download_exception}")
    return False


def _generate_alto(pdf_location, work_folder):
    pages = _get_pdf_page_count(pdf_location)
    logger.debug(f"Processing {pdf_location}, which has {pages} pages")

    alto_folder = Path(work_folder, 'alto')
    alto_folder.mkdir()
    for i in range(1, pages + 1):
        logger.debug(f"Processing page {i}")
        output = Path(alto_folder, f"{i}.xml")
        command = f"/usr/bin/pdfalto -readingOrder -noImage -f {i} -l {i} {pdf_location} {output}"
        logger.debug(f"running {command}")
        subprocess.run(command, shell=True, check=True, stdout=PIPE, stderr=PIPE)

        # rescale Alto


def _get_pdf_page_count(pdf):
    logger.debug(f'getting size of {pdf}')
    pdf = open(pdf, 'rb')
    parser = PDFParser(pdf)
    document = PDFDocument(parser)
    pages = int(resolve1(document.catalog['Pages'])['Count'])
    return pages


def _rm_tree(pth: Path):
    for child in pth.iterdir():
        if child.is_file():
            child.unlink()
        else:
            _rm_tree(child)
    pth.rmdir()


if __name__ == "__main__":
    args = sys.argv[1:]
    extract_alto(args[0], args[1])
