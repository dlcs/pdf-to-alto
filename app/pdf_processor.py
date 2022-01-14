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
        target_file = Path(work_folder, pdf_location.split("/")[-1])
        downloaded_pdf = _download_pdf(pdf_location, target_file)

        if not downloaded_pdf:
            logger.error("Unable to download PDF")
            return False

        _generate_alto(target_file, work_folder, pdf_identifier)
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


def _generate_alto(pdf_location, work_folder, pdf_identifier):
    pages = _get_pdf_page_count(pdf_location)
    logger.debug(f"Processing {pdf_location}, which has {pages} pages")

    alto_folder = Path(work_folder, 'alto')
    alto_folder.mkdir(exist_ok=True)
    for i in range(1, pages + 1):
        logger.debug(f"Processing page {i}")
        output = Path(alto_folder, f"{pdf_identifier}-{i - 1:04d}.xml")
        flags = '' if RESCALE_ALTO else '-noImage'
        command = f"/usr/bin/pdfalto -readingOrder {flags} -f {i} -l {i} {pdf_location} {output}"
        logger.debug(f"running {command}")
        subprocess.run(command, shell=True, check=True, stdout=PIPE, stderr=PIPE)

        if RESCALE_ALTO:
            logger.debug(f"Rescaling page {i}")
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

    page.set("WIDTH", str(scale_w * page_width))
    page.set("HEIGHT", str(scale_h * page_height))

    for el in page.iter(f'{ns}TextBlock', f'{ns}TextLine', f'{ns}String', f'{ns}SP'):
        _scale_element(el, scale_w, width, True)
        _scale_element(el, scale_h, height, False)

    alto_file.rename(str(alto_file).replace(".xml", ".orig.xml"))
    alto_tree.write(str(alto_file))


def _scale_element(el, scale: float, max_dimension: float, width: bool):
    if width:
        dimension_attr = "WIDTH"
        position_attr = "HPOS"
    else:
        dimension_attr = "HEIGHT"
        position_attr = "VPOS"

    dimension = el.get(dimension_attr)
    position = el.get(position_attr)

    new_d = _scale_value(dimension, scale)
    new_p = _scale_value(position, scale)

    if new_p + new_d > max_dimension:
        overlap = (new_p + new_d) - max_dimension
        logger.warn(f"Rescaling {el} will result in out of bounds dimension, reducing {dimension_attr} by {overlap}")
        new_d = new_d - overlap

    # NOTE space doesn't have dimension
    if new_d:
        el.set(dimension_attr, str(int(new_d)))

    if new_p:
        el.set(position_attr, str(int(new_p)))


def _scale_value(current: str, scale: float) -> int:
    if not current:
        return 0

    return int(scale * float(current))


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
