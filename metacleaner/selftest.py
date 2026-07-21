# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

import pymupdf as fitz
from PIL import Image

from .engine import clean_file, inspect_file


def run_engine_smoke_test() -> int:
    """Exercise packaged PDF and image native libraries without showing UI."""
    try:
        with tempfile.TemporaryDirectory(prefix="metacleaner-smoke-") as folder:
            root = Path(folder)

            pdf_path = root / "sample.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "PACKAGE-SMOKE-CONTENT")
            document.set_metadata({"author": "Smoke Author", "title": "Keep Title"})
            document.save(pdf_path)
            document.close()
            pdf_result = clean_file(pdf_path)
            if not pdf_result.success or not pdf_result.output:
                return 11
            with fitz.open(pdf_result.output) as cleaned_pdf:
                if "PACKAGE-SMOKE-CONTENT" not in cleaned_pdf[0].get_text():
                    return 12
                if cleaned_pdf.metadata.get("author"):
                    return 13

            image_path = root / "sample.jpg"
            image = Image.new("RGB", (24, 16), (17, 93, 151))
            exif = Image.Exif()
            exif[315] = "Smoke Author"
            image.save(image_path, quality=90, exif=exif)
            image_result = clean_file(image_path)
            if not image_result.success or not image_result.output:
                return 21
            with Image.open(image_result.output) as cleaned_image:
                if cleaned_image.size != (24, 16) or cleaned_image.getexif():
                    return 22

            for extension, code in ((".tiff", 23), (".webp", 24)):
                plugin_path = root / f"plugin{extension}"
                plugin_exif = Image.Exif()
                plugin_exif[315] = "Plugin Smoke Author"
                image.save(plugin_path, exif=plugin_exif)
                plugin_result = clean_file(plugin_path)
                if not plugin_result.success or not plugin_result.output:
                    return code
                with Image.open(plugin_result.output) as cleaned_plugin:
                    if cleaned_plugin.size != (24, 16):
                        return code + 10
                if inspect_file(plugin_result.output).personal_count:
                    return code + 10

            if inspect_file(pdf_result.output).personal_count:
                return 31

            docx_path = root / "typed-dates.docx"
            parts = {
                "[Content_Types].xml": b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="xml" ContentType="application/xml"/>
 <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
 <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
 <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
                "_rels/.rels": b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
 <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
 <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
                "docProps/core.xml": b"""<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <dc:creator>Smoke Author</dc:creator><cp:lastModifiedBy>Smoke Editor</cp:lastModifiedBy>
 <dcterms:created xsi:type="dcterms:W3CDTF">2021-12-20T12:14:00Z</dcterms:created>
 <dcterms:modified xsi:type="dcterms:W3CDTF">2026-06-30T05:51:00Z</dcterms:modified>
</cp:coreProperties>""",
                "docProps/app.xml": b"""<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
 <Template>Normal.dotm</Template><Company>Smoke Lab</Company><Application>Microsoft Office Word</Application>
</Properties>""",
                "word/document.xml": b"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:body><w:p><w:r><w:t>PACKAGE-SMOKE-DOCX</w:t></w:r></w:p><w:sectPr/></w:body>
</w:document>""",
            }
            with ZipFile(docx_path, "w", compression=ZIP_DEFLATED) as package:
                for name, data in parts.items():
                    package.writestr(name, data)
            docx_result = clean_file(docx_path)
            if not docx_result.success or not docx_result.output:
                return 41
            with ZipFile(docx_result.output) as package:
                core = ET.fromstring(package.read("docProps/core.xml"))
                core_names = {elem.tag.rsplit("}", 1)[-1] for elem in core}
                if {"creator", "lastModifiedBy", "created", "modified"} & core_names:
                    return 42
                app = ET.fromstring(package.read("docProps/app.xml"))
                app_names = {elem.tag.rsplit("}", 1)[-1] for elem in app}
                if {"Template", "Company"} & app_names:
                    return 43
        return 0
    except Exception:
        return 99
