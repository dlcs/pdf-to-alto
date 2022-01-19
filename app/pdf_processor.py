import subprocess
import sys
import traceback
import uuid

import fitz
import requests

from subprocess import PIPE

from botocore.exceptions import ClientError
from lxml import etree
from logzero import logger
from pathlib import Path

from app.aws_factory import get_aws_client
from app.settings import (
    DOWNLOAD_CHUNK_SIZE,
    RESCALE_ALTO,
    REMOVE_WORK_DIR,
    WORKING_FOLDER,
    PREPEND_ID,
)

s3 = get_aws_client("s3")


class PDFProcessor:
    def __init__(self, pdf_location: str, pdf_identifier: str, output_location: str):
        """
        Create new PDFProcessor object
        :param pdf_location: URI where PDF can be downloaded from
        :param pdf_identifier: Unique identifier for PDF
        """

        self.generated_alto = []
        self.pdf_location = pdf_location
        self.pdf_identifier = pdf_identifier

        if output_location:
            out_split = output_location.replace("s3://", "").split("/")
            self.bucket = out_split[0]
            self.prefix = str.join("/", out_split[1:])
        else:
            self.bucket = None
            self.prefix = None

    def extract_alto(self) -> bool:
        """
        Extract METS ALTO file per page of PDF
        :return: boolean indicating success
        """

        logger.info(f"Processing {self.pdf_location} with id {self.pdf_identifier}")
        work_folder = self._create_work_folder()

        try:
            target_file = Path(work_folder, self.pdf_location.split("/")[-1])
            downloaded_pdf = self._download_pdf(target_file)

            if not downloaded_pdf:
                logger.error("Unable to download PDF")
                return False

            self._generate_alto(target_file, work_folder)
            self._upload_to_s3()
            return True
        except Exception:
            e = traceback.format_exc()
            logger.error(f"Error extracting ALTO from PDF: {e}")
            return False
        finally:
            if REMOVE_WORK_DIR:
                logger.debug(f"Cleaning up folder {work_folder}")
                _rm_tree(work_folder)

    def _create_work_folder(self):
        work_folder = Path(WORKING_FOLDER, self.pdf_identifier, generate_guid())
        work_folder.mkdir(parents=True, exist_ok=False)
        return work_folder

    def _download_pdf(self, target_file: Path):
        try:
            download_request = requests.get(self.pdf_location, stream=True)
            with open(target_file, "wb") as file:
                for chunk in download_request.iter_content(DOWNLOAD_CHUNK_SIZE):
                    file.write(chunk)
            return True
        except Exception as download_exception:
            logger.exception(
                f"problem during download of {self.pdf_location} to {target_file}: {download_exception}"
            )
        return False

    def _generate_alto(self, pdf: Path, work_folder: Path):
        pdf_attrs = self._get_pdf_page_attributes(pdf)
        logger.debug(f"Processing {pdf}, which has {len(pdf_attrs)} pages")

        alto_folder = Path(work_folder, "alto")
        alto_folder.mkdir(exist_ok=True)

        for i, dimensions in pdf_attrs.items():
            page_num = i + 1
            logger.debug(f"Processing page {page_num}")
            xml_file = f"{i:04d}.xml"
            if PREPEND_ID:
                xml_file = f"{self.pdf_identifier}-{xml_file}"
            output = Path(alto_folder, xml_file)
            command = f"/usr/bin/pdfalto -readingOrder -noImage -f {page_num} -l {page_num} {pdf} {output}"
            logger.debug(f"running {command}")
            subprocess.run(command, shell=True, check=True, stdout=PIPE, stderr=PIPE)

            if RESCALE_ALTO:
                width, height = dimensions
                logger.debug(f"Rescaling page {page_num} to {width} x {height} (w x h)")
                self._rescale_alto(output, width, height)

            self.generated_alto.append(output)

    @staticmethod
    def _get_pdf_page_attributes(pdf: str) -> dict:
        logger.debug(f"getting page and image attributes for {pdf}")
        doc = fitz.open(pdf)

        if not RESCALE_ALTO:
            # if not rescaling we don't care about page dimensions
            return {i: [] for i in range(len(doc))}

        pdf_addrs = {}
        for i in range(len(doc)):
            for img in doc.get_page_images(i):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                pdf_addrs[i] = [pix.w, pix.h]

        return pdf_addrs

    def _rescale_alto(self, alto_file: Path, width: int, height: int):
        ns = "{http://www.loc.gov/standards/alto/ns-v3#}"

        parser = etree.XMLParser(remove_blank_text=True)
        alto_tree = etree.parse(str(alto_file), parser)
        root = alto_tree.getroot()
        layout = root.find(f"{ns}Layout")
        page = layout.find(f"{ns}Page")
        page_width = int(float(page.get("WIDTH")))
        page_height = int(float(page.get("HEIGHT")))

        if width == page_width and height == page_height:
            logger.info("Page width and height are as expected, no rescaling required")

        scale_w = width / page_width
        scale_h = height / page_height

        page.set("WIDTH", str(scale_w * page_width))
        page.set("HEIGHT", str(scale_h * page_height))

        for el in page.iter(
            f"{ns}TextBlock", f"{ns}TextLine", f"{ns}String", f"{ns}SP"
        ):
            self._scale_element(el, scale_w, width, True)
            self._scale_element(el, scale_h, height, False)

        alto_file.rename(str(alto_file).replace(".xml", ".orig.xml"))
        alto_tree.write(str(alto_file))

    def _scale_element(self, el, scale: float, max_dimension: float, width: bool):
        if width:
            dimension_attr = "WIDTH"
            position_attr = "HPOS"
        else:
            dimension_attr = "HEIGHT"
            position_attr = "VPOS"

        dimension = el.get(dimension_attr)
        position = el.get(position_attr)

        new_d = self._scale_value(dimension, scale)
        new_p = self._scale_value(position, scale)

        if new_p + new_d > max_dimension:
            overlap = (new_p + new_d) - max_dimension
            logger.debug(
                f"Rescaling {el} will result in out of bounds dimension, reducing {dimension_attr} by {overlap}"
            )
            new_d = new_d - overlap

        # NOTE <Space/> elements don't have height dimensions
        if new_d:
            el.set(dimension_attr, str(int(new_d)))

        if new_p:
            el.set(position_attr, str(int(new_p)))

    @staticmethod
    def _scale_value(current: str, scale: float) -> int:
        if not current:
            return 0

        return int(scale * float(current))

    def _upload_to_s3(self):
        if not self.bucket:
            return True

        success = True
        logger.info(
            f"Uploading {len(self.generated_alto)} alto files to s3://{self.bucket}/{self.prefix}/"
        )
        for o in self.generated_alto:
            try:
                response = s3.upload_file(
                    str(o), self.bucket, f"{self.prefix}/{o.name}"
                )
            except ClientError as e:
                logger.error("Failed to upload {o}. {e}")
                success = False

        return success


def _rm_tree(pth: Path):
    for child in pth.iterdir():
        if child.is_file():
            child.unlink()
        else:
            _rm_tree(child)
    pth.rmdir()


def generate_guid():
    return str(uuid.uuid4())


if __name__ == "__main__":
    args = sys.argv[1:]
    processor = PDFProcessor(args[0], args[1])
    processor.extract_alto()
    print(processor.generated_alto)
