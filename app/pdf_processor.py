import os
import subprocess
import sys
import traceback
import uuid

import imagesize
import requests

from subprocess import PIPE
from lxml import etree
from logzero import logger
from pathlib import Path
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import resolve1

DOWNLOAD_CHUNK_SIZE = int(os.environ.get('DOWNLOAD_CHUNK_SIZE', 2048))
WORKING_FOLDER = os.environ.get('WORKING_FOLDER', './work')
REMOVE_WORK_DIR = os.environ.get('REMOVE_WORK_DIR', 'True').lower() in ('true', 't', '1')
RESCALE_ALTO = os.environ.get('RESCALE_ALTO', 'True').lower() in ('true', 't', '1')


def extract_alto(pdf_location, pdf_identifier):
    logger.info(f"Processing {pdf_location} with id {pdf_identifier}")
    work_folder = _create_work_folder(pdf_identifier)

    try:
        target_file = Path(work_folder, f"{pdf_identifier}.pdf")
        downloaded_pdf = _download_pdf(pdf_location, target_file)

        if not downloaded_pdf:
            logger.error("Unable to download PDF")
            return False

        _generate_alto(target_file, work_folder)
        return True
    except Exception:
        e = traceback.format_exc()
        logger.error(f"Error extracting ALTO from PDF: {e}")
        return False
    finally:
        if REMOVE_WORK_DIR:
            logger.debug(f'Cleaning up folder {work_folder}')
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
            for chunk in download_request.iter_content(DOWNLOAD_CHUNK_SIZE):
                file.write(chunk)
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
        command = f"/usr/bin/pdfalto -readingOrder -f {i} -l {i} {pdf_location} {output}"
        logger.debug(f"running {command}")
        subprocess.run(command, shell=True, check=True, stdout=PIPE, stderr=PIPE)

        if RESCALE_ALTO:
            _rescale_alto(output)


def _get_pdf_page_count(pdf):
    logger.debug(f'getting page count for {pdf}')
    pdf = open(pdf, 'rb')
    parser = PDFParser(pdf)
    document = PDFDocument(parser)
    pages = int(resolve1(document.catalog['Pages'])['Count'])
    return pages


def _rescale_alto(alto_file: Path):
    # NOTE - expectation is a single image per page
    width, height = _get_image_size(alto_file)

    if not width or not height:
        return

    ns = "{http://www.loc.gov/standards/alto/ns-v3#}"

    parser = etree.XMLParser(remove_blank_text=True)
    alto_tree = etree.parse(str(alto_file), parser)
    root = alto_tree.getroot()
    layout = root.find(f'{ns}Layout')
    page = layout.find(f'{ns}Page')
    page_width = int(float(page.get("WIDTH")))
    page_height = int(float(page.get("HEIGHT")))

    if width == page_width and height == page_height:
        logger.info("Page width and height are as expected, no rescaling required")

    scale_w = width / page_width
    scale_h = height / page_height

    _set_scaled_attr(page, "WIDTH", scale_w)
    _set_scaled_attr(page, "HEIGHT", scale_h)

    for el in page.iter(f'{ns}TextBlock', f'{ns}TextLine', f'{ns}String', f'{ns}SP'):
        _set_scaled_attr(el, "WIDTH", scale_w)
        _set_scaled_attr(el, "HPOS", scale_w)
        _set_scaled_attr(el, "HEIGHT", scale_h)
        _set_scaled_attr(el, "VPOS", scale_h)

    alto_file.rename(str(alto_file).replace(".xml", ".orig.xml"))
    alto_tree.write(str(alto_file))


def _set_scaled_attr(el, attr_name, scale):
    if attr_val := el.get(attr_name):
        el.set(attr_name, str(int(scale * float(attr_val))))


def _get_image_size(alto_file: Path):
    # NOTE - expectation is a single image per page
    target_image = Path(f"{alto_file}_data", "image-1.png")
    width = 0
    height = 0
    try:
        width, height = imagesize.get(target_image)
    except FileNotFoundError:
        logger.info(f"Attempt to rescale {alto_file} failed as image {target_image} not found")

    return width, height


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
