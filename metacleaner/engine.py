# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import os
import posixpath
import tempfile
from typing import Iterable
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo
import xml.etree.ElementTree as ET

import pymupdf as fitz
from PIL import ExifTags, Image, ImageOps, JpegImagePlugin

from .models import CleanMode, CleanOptions, CleanResult, InspectionResult, MetadataItem


OOXML_EXTENSIONS = {
    ".docx", ".docm", ".dotx", ".dotm",
    ".xlsx", ".xlsm", ".xltx", ".xltm",
    ".pptx", ".pptm", ".potx", ".potm", ".ppsx", ".ppsm",
}
ODF_EXTENSIONS = {".odt", ".ods", ".odp", ".odg"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
SUPPORTED_EXTENSIONS = OOXML_EXTENSIONS | ODF_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS

NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcmitype": "http://purl.org/dc/dcmitype/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "dc_odf": "http://purl.org/dc/elements/1.1/",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
}
for prefix, uri in NS.items():
    if prefix not in {"ep", "dc_odf"}:
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass

CORE_PERSONAL = {"creator", "lastModifiedBy", "created", "modified", "lastPrinted"}
CORE_DESCRIPTIVE = {
    "title", "subject", "description", "keywords", "category",
    "contentStatus", "identifier", "language", "version", "revision",
}
APP_PERSONAL = {"Manager", "Company", "Template", "HyperlinkBase"}
APP_TECHNICAL = {"Application", "AppVersion"}
REVIEW_ELEMENTS = {
    "comment", "commentEx", "commentExtensible", "ins", "del", "moveFrom",
    "moveTo", "rPrChange", "pPrChange", "sectPrChange", "tblPrChange",
    "tblGridChange", "trPrChange", "tcPrChange", "numberingChange", "cellDel",
    "cellIns", "cellMerge", "cmAuthor", "person", "threadedComment",
    "presenceInfo",
    "moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
    "customXmlInsRangeStart", "customXmlInsRangeEnd",
    "customXmlDelRangeStart", "customXmlDelRangeEnd",
    "customXmlMoveFromRangeStart", "customXmlMoveFromRangeEnd",
    "customXmlMoveToRangeStart", "customXmlMoveToRangeEnd",
    "conflictIns", "conflictDel", "cm",
}
REVIEW_ATTRS = {
    "author", "initials", "date", "dateUtc", "displayName", "userId",
    "providerId", "email", "name", "dT", "dt",
}
PERSONAL_PDF_KEYS = {"author", "creator", "producer", "creationDate", "modDate"}
ALL_PDF_KEYS = PERSONAL_PDF_KEYS | {"title", "subject", "keywords", "trapped"}
PDF_INFO_STANDARD_KEYS = {
    "Title", "Author", "Subject", "Keywords", "Creator", "Producer",
    "CreationDate", "ModDate", "Trapped",
}
PDF_INFO_PERSONAL_KEYS = {"Author", "Creator", "Producer", "CreationDate", "ModDate"}
XMP_SAFE_PROPERTIES = {
    # Deliberately qualified allow-list. A malicious vendor namespace cannot
    # smuggle data through by reusing a safe local name such as ``title``.
    ("http://purl.org/dc/elements/1.1/", "title"),
    ("http://purl.org/dc/elements/1.1/", "description"),
    ("http://purl.org/dc/elements/1.1/", "subject"),
    ("http://purl.org/dc/elements/1.1/", "format"),
    ("http://ns.adobe.com/pdf/1.3/", "Keywords"),
    # Preserve PDF/A, PDF/UA and extension-schema conformance declarations.
    ("http://www.aiim.org/pdfa/ns/id/", "part"),
    ("http://www.aiim.org/pdfa/ns/id/", "conformance"),
    ("http://www.aiim.org/pdfa/ns/id/", "amd"),
    ("http://www.aiim.org/pdfa/ns/id/", "rev"),
    ("http://www.aiim.org/pdfua/ns/id/", "part"),
    ("http://www.aiim.org/pdfua/ns/id/", "amd"),
    ("http://www.aiim.org/pdfua/ns/id/", "rev"),
    ("http://www.aiim.org/pdfa/ns/extension/", "schemas"),
}
ODF_META_PERSONAL = {
    "creator", "initial-creator", "creation-date", "date", "printed-by",
    "print-date", "editing-duration", "editing-cycles", "user-defined",
    "template", "auto-reload",
}
ODF_META_DESCRIPTIVE = {"title", "subject", "description", "keyword", "generator"}
ODF_REVIEW_CONTAINERS = {"annotation", "change-info"}
IMAGE_TECHNICAL_EXIF = {
    "ImageWidth", "ImageLength", "BitsPerSample", "Compression",
    "PhotometricInterpretation", "Thresholding", "CellWidth", "CellLength",
    "FillOrder", "StripOffsets", "SamplesPerPixel", "RowsPerStrip",
    "StripByteCounts", "XResolution", "YResolution", "PlanarConfiguration",
    "ResolutionUnit", "TransferFunction", "WhitePoint", "PrimaryChromaticities",
    "YCbCrCoefficients", "YCbCrSubSampling", "YCbCrPositioning",
    "ReferenceBlackWhite", "TileWidth", "TileLength", "TileOffsets",
    "TileByteCounts", "ExtraSamples", "SampleFormat", "SMinSampleValue",
    "SMaxSampleValue", "ColorMap", "Predictor", "Orientation",
    "InterColorProfile",
}


class MetadataCleanError(RuntimeError):
    pass


class SignedFileError(MetadataCleanError):
    pass


class EncryptedFileError(MetadataCleanError):
    pass


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":")[-1]


def namespace_name(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") and "}" in tag else ""


def _is_neutral_review_id(value: str) -> bool:
    compact = value.strip("{}").replace("-", "").casefold()
    return len(compact) == 32 and compact[:20] == "0" * 20 and all(
        character in "0123456789abcdef" for character in compact[20:]
    )


def display_value(value: object, limit: int = 100) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in OOXML_EXTENSIONS:
        return "Office 文档"
    if suffix in ODF_EXTENSIONS:
        return "OpenDocument"
    if suffix in PDF_EXTENSIONS:
        return "PDF"
    if suffix in IMAGE_EXTENSIONS:
        return "图片"
    return "不支持"


def iter_supported_files(folder: Path, recursive: bool = True) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        (p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: str(p).lower(),
    )


def _xml_root(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def _serialize(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _namespace_declarations(data: bytes) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for _event, (prefix, uri) in ET.iterparse(BytesIO(data), events=("start-ns",)):
        declarations.setdefault(prefix or "", uri)
    return declarations


def _validate_ignorable_prefixes(data: bytes) -> None:
    declarations = _namespace_declarations(data)
    root = _xml_root(data)
    for elem in root.iter():
        for attr, value in elem.attrib.items():
            if local_name(attr) != "Ignorable":
                continue
            missing = sorted({prefix for prefix in value.split() if prefix not in declarations})
            if missing:
                raise MetadataCleanError(
                    "审阅 XML 的 mc:Ignorable 引用了未声明命名空间：" + ", ".join(missing)
                )


def _serialize_preserving_namespaces(root: ET.Element, original: bytes) -> bytes:
    original_declarations = _namespace_declarations(original)
    for prefix, uri in original_declarations.items():
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            # ElementTree reserves ns0/ns1-style prefixes.  They are restored
            # as redundant declarations below if a QName-valued attribute
            # still references them.
            pass

    result = _serialize(root)
    serialized_declarations = _namespace_declarations(result)
    missing_named = [
        (prefix, uri)
        for prefix, uri in original_declarations.items()
        if prefix and serialized_declarations.get(prefix) != uri
    ]
    if missing_named:
        declaration_end = result.find(b"?>")
        root_start = result.find(b"<", declaration_end + 2)
        root_close = result.find(b">", root_start)
        insert_at = root_close - 1 if result[root_close - 1 : root_close] == b"/" else root_close
        additions = b"".join(
            b' xmlns:' + prefix.encode("utf-8") + b'="' + uri.encode("utf-8") + b'"'
            for prefix, uri in missing_named
        )
        result = result[:insert_at] + additions + result[insert_at:]

    _xml_root(result)
    _validate_ignorable_prefixes(result)
    return result


def _serialize_with_default_namespace(root: ET.Element) -> bytes:
    """Serialize an OPC control part with a conventional default namespace.

    ElementTree's ``default_namespace`` option rejects the unqualified
    attributes used by OPC.  Serialize normally, then remove only the root
    namespace's generated element prefix while leaving attributes and any
    secondary namespaces untouched.
    """
    if not root.tag.startswith("{") or "}" not in root.tag:
        return _serialize(root)
    namespace = root.tag[1:].split("}", 1)[0]
    data = _serialize(root)
    declaration_end = data.find(b"?>")
    root_start = data.find(b"<", declaration_end + 2)
    root_end = data.find(b" ", root_start)
    close_end = data.find(b">", root_start)
    if root_end < 0 or (0 <= close_end < root_end):
        root_end = close_end
    qname = data[root_start + 1 : root_end]
    if b":" not in qname:
        return data
    prefix = qname.split(b":", 1)[0]
    namespace_bytes = namespace.encode("utf-8")
    declaration = b'xmlns:' + prefix + b'="' + namespace_bytes + b'"'
    # Keep the prefixed declaration as a redundant binding.  It is required
    # if a rare producer used qualified attributes in the same namespace.
    result = (
        data.replace(b"<" + prefix + b":", b"<")
        .replace(b"</" + prefix + b":", b"</")
        .replace(declaration, b'xmlns="' + namespace_bytes + b'" ' + declaration)
    )
    _xml_root(result)
    return result


def _serialized_root_qname(data: bytes) -> bytes:
    payload = data.lstrip()
    if payload.startswith(b"<?xml"):
        declaration_end = payload.find(b"?>")
        payload = payload[declaration_end + 2 :].lstrip()
    if not payload.startswith(b"<"):
        return b""
    end = len(payload)
    for marker in (b" ", b">", b"/"):
        index = payload.find(marker, 1)
        if index >= 0:
            end = min(end, index)
    return payload[1:end]


def _clone_zip_info(info: ZipInfo) -> ZipInfo:
    # ZIP member timestamps, comments and extra fields can themselves expose
    # workstation/user history.  Use a deterministic neutral timestamp while
    # preserving package-critical compression and permission attributes.
    copied = ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
    copied.compress_type = info.compress_type
    copied.comment = b""
    copied.extra = b""
    copied.internal_attr = info.internal_attr
    copied.external_attr = info.external_attr
    copied.create_system = info.create_system
    copied.create_version = info.create_version
    copied.extract_version = info.extract_version
    copied.flag_bits = info.flag_bits
    copied.volume = info.volume
    return copied


def _zip_is_signed(names: Iterable[str]) -> bool:
    lowered = {name.lower() for name in names}
    return any(
        name.startswith("_xmlsignatures/")
        or name.startswith("meta-inf/documentsignatures")
        or name.startswith("meta-inf/macrosignatures")
        for name in lowered
    )


def _root_relationship_parts(zf: ZipFile) -> dict[str, set[str]]:
    """Resolve privacy-relevant package parts from root relationships."""
    resolved = {
        "custom-properties": set(),
        "core-properties": set(),
        "extended-properties": set(),
        "thumbnail": set(),
    }
    if "_rels/.rels" not in zf.namelist():
        return resolved
    try:
        root = _xml_root(zf.read("_rels/.rels"))
    except ET.ParseError:
        return resolved
    for relation in root:
        if relation.attrib.get("TargetMode", "").casefold() == "external":
            continue
        relation_type = relation.attrib.get("Type", "").casefold()
        target = relation.attrib.get("Target", "").replace("\\", "/")
        normalized = posixpath.normpath("/" + target).lstrip("/")
        if not target or normalized.startswith("../"):
            continue
        for ending in resolved:
            if relation_type.endswith("/" + ending):
                resolved[ending].add(normalized)
    return resolved


def _inspect_ooxml(path: Path) -> InspectionResult:
    result = InspectionResult(path, "Office 文档", True)
    try:
        with ZipFile(path) as zf:
            names = set(zf.namelist())
            related = _root_relationship_parts(zf)
            bad = zf.testzip()
            if bad:
                raise MetadataCleanError(f"压缩包损坏：{bad}")
            result.signed = _zip_is_signed(names)
            if result.signed:
                result.warnings.append("检测到数字签名；为避免产生无效签名，默认跳过。")
            core_parts = ({"docProps/core.xml"} | related["core-properties"]) & names
            for core_part in core_parts:
                root = _xml_root(zf.read(core_part))
                for child in root:
                    name = local_name(child.tag)
                    value = display_value(child.text)
                    if value:
                        result.items.append(MetadataItem("核心属性", name, value, name in CORE_PERSONAL))
            app_parts = ({"docProps/app.xml"} | related["extended-properties"]) & names
            for app_part in app_parts:
                root = _xml_root(zf.read(app_part))
                for child in root:
                    name = local_name(child.tag)
                    if name not in APP_PERSONAL | APP_TECHNICAL:
                        continue
                    value = display_value(child.text)
                    if value:
                        result.items.append(MetadataItem("扩展属性", name, value, name in APP_PERSONAL))
            custom_parts = ({"docProps/custom.xml"} | related["custom-properties"]) & names
            for custom_part in custom_parts:
                root = _xml_root(zf.read(custom_part))
                for prop in root:
                    name = prop.attrib.get("name", "自定义属性")
                    value = display_value("".join(prop.itertext()))
                    result.items.append(MetadataItem("自定义属性", name, value or "（空值）", True))
            thumbnails = {
                name for name in names if name.lower().startswith("docprops/thumbnail.")
            } | (related["thumbnail"] & names)
            for name in thumbnails:
                result.items.append(MetadataItem("预览", "文档缩略图", name, True))
            _inspect_ooxml_reviewers(zf, result)
            if any(name.lower().endswith("vbaprojectsignature.bin") for name in names):
                result.warnings.append("检测到 VBA 项目签名；宏内容会保留，但建议在 Office 中复核签名状态。")
    except (OSError, BadZipFile, ET.ParseError, ValueError, MetadataCleanError) as exc:
        result.supported = False
        result.warnings.append(f"无法读取 Office 文件：{exc}")
    return result


def _inspect_ooxml_reviewers(zf: ZipFile, result: InspectionResult) -> None:
    seen: set[tuple[str, str]] = set()
    for name in zf.namelist():
        low = name.lower()
        if not low.startswith(("word/", "xl/", "ppt/")) or not low.endswith(".xml"):
            continue
        try:
            root = _xml_root(zf.read(name))
        except ET.ParseError:
            continue
        for elem in root.iter():
            lname = local_name(elem.tag)
            author_part = any(token in low for token in ("comment", "people", "person", "author"))
            if author_part and lname == "author" and elem.text and display_value(elem.text) not in {"Anonymous", "匿名"}:
                key = ("批注/审阅作者", display_value(elem.text))
                if key not in seen:
                    result.items.append(MetadataItem("审阅信息", key[0], key[1], True))
                    seen.add(key)
            if lname not in REVIEW_ELEMENTS:
                continue
            for attr, value in elem.attrib.items():
                aname = local_name(attr)
                text = display_value(value)
                if lname == "person" and aname == "id":
                    if text and not _is_neutral_review_id(text):
                        key = ("person.id", text)
                        if key not in seen:
                            result.items.append(MetadataItem("审阅信息", key[0], key[1], True))
                            seen.add(key)
                    continue
                if lname == "threadedComment" and aname == "personId":
                    if text and not _is_neutral_review_id(text):
                        key = ("threadedComment.personId", text)
                        if key not in seen:
                            result.items.append(MetadataItem("审阅信息", key[0], key[1], True))
                            seen.add(key)
                    continue
                if aname in REVIEW_ATTRS and text and text not in {"Anonymous", "匿名"}:
                    key = (f"{lname}.{aname}", text)
                    if key not in seen:
                        result.items.append(MetadataItem("审阅信息", key[0], key[1], True))
                        seen.add(key)


def _inspect_odf(path: Path) -> InspectionResult:
    result = InspectionResult(path, "OpenDocument", True)
    try:
        with ZipFile(path) as zf:
            names = set(zf.namelist())
            bad = zf.testzip()
            if bad:
                raise MetadataCleanError(f"压缩包损坏：{bad}")
            result.encrypted = _odf_is_encrypted(zf)
            if result.encrypted:
                result.warnings.append("检测到 OpenDocument 加密成员，无法安全处理。")
                return result
            result.signed = _zip_is_signed(names)
            if result.signed:
                result.warnings.append("检测到 OpenDocument 数字签名；默认跳过。")
            for part in ("meta.xml", "content.xml"):
                if part not in names:
                    continue
                root = _xml_root(zf.read(part))
                if part == "content.xml":
                    _inspect_odf_reviewers(root, result)
                    continue
                for elem in root.iter():
                    lname = local_name(elem.tag)
                    value = display_value(elem.text)
                    if lname in {"template", "auto-reload"}:
                        value = display_value(elem.attrib.get(f"{{{NS['xlink']}}}href", "")) or value
                    if not value:
                        continue
                    if lname in ODF_META_PERSONAL:
                        if lname == "user-defined":
                            prop_name = elem.attrib.get(f"{{{NS['meta']}}}name", "自定义属性")
                            result.items.append(MetadataItem("自定义属性", prop_name, value, True))
                        else:
                            result.items.append(MetadataItem("OpenDocument 元数据", lname, value, True))
                    elif lname in ODF_META_DESCRIPTIVE:
                        result.items.append(MetadataItem("OpenDocument 元数据", lname, value, False))
    except (OSError, BadZipFile, ET.ParseError, ValueError, MetadataCleanError) as exc:
        result.supported = False
        result.warnings.append(f"无法读取 OpenDocument：{exc}")
    return result


def _odf_is_encrypted(zf: ZipFile) -> bool:
    manifest_name = "META-INF/manifest.xml"
    if manifest_name not in zf.namelist():
        return False
    try:
        root = _xml_root(zf.read(manifest_name))
    except ET.ParseError as exc:
        raise MetadataCleanError(f"OpenDocument manifest 无法解析：{exc}") from exc
    return any(local_name(elem.tag) in {"encryption-data", "encrypted-key"} for elem in root.iter())


def _inspect_odf_reviewers(root: ET.Element, result: InspectionResult) -> None:
    """Inspect only review containers, never visible text fields such as text:date."""
    seen: set[tuple[str, str]] = set()

    def visit(elem: ET.Element, in_review: bool = False) -> None:
        current_review = in_review or local_name(elem.tag) in ODF_REVIEW_CONTAINERS
        if (
            current_review
            and namespace_name(elem.tag) == NS["dc_odf"]
            and local_name(elem.tag) in {"creator", "date"}
        ):
            value = display_value(elem.text)
            key = (local_name(elem.tag), value)
            if value and key not in seen:
                result.items.append(MetadataItem("OpenDocument 审阅信息", key[0], key[1], True))
                seen.add(key)
        for child in elem:
            visit(child, current_review)

    visit(root)


def _pdf_has_signatures(doc: fitz.Document) -> bool:
    try:
        # PyMuPDF returns -1 when the PDF has no AcroForm.  Only positive
        # bit flags indicate that signature fields/signatures are present.
        if doc.get_sigflags() > 0:
            return True
    except Exception:
        pass
    for page in doc:
        widgets = page.widgets()
        if widgets:
            for widget in widgets:
                if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                    return True
    return False


def _pdf_info_xref(doc: fitz.Document) -> int:
    try:
        kind, value = doc.xref_get_key(-1, "Info")
        if kind == "xref":
            return int(value.split()[0])
    except Exception:
        pass
    return 0


def _pdf_is_encrypted(doc: fitz.Document) -> bool:
    """Treat any encryption dictionary as encrypted, even with an empty user password."""
    try:
        encrypt_kind, encrypt_value = doc.xref_get_key(-1, "Encrypt")
        if encrypt_kind != "null" and encrypt_value not in {"", "null"}:
            return True
    except Exception:
        # Fall back to PyMuPDF's state flags for malformed or unusual trailers.
        pass
    return bool(getattr(doc, "is_encrypted", False) or doc.needs_pass)


def _inspect_pdf_xmp(xml_text: str, result: InspectionResult) -> None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        result.items.append(MetadataItem("PDF XMP", "无法解析的 XMP 元数据", "存在", True))
        result.warnings.append("XMP 元数据无法解析；清理时将移除该 XMP 数据块。")
        return
    seen: set[tuple[str, str]] = set()
    for description in root.iter():
        if local_name(description.tag) != "Description":
            continue
        for attr, raw_value in description.attrib.items():
            name = local_name(attr)
            qualified = (namespace_name(attr), name)
            if qualified == ("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "about"):
                continue
            value = display_value(raw_value)
            if value and (name, value) not in seen:
                result.items.append(MetadataItem("PDF XMP", name, value, qualified not in XMP_SAFE_PROPERTIES))
                seen.add((name, value))
        for prop in list(description):
            name = local_name(prop.tag)
            qualified = (namespace_name(prop.tag), name)
            value = display_value(" ".join(prop.itertext()))
            if value and (name, value) not in seen:
                result.items.append(MetadataItem("PDF XMP", name, value, qualified not in XMP_SAFE_PROPERTIES))
                seen.add((name, value))


def _sanitize_xmp_personal(xml_text: str) -> str | None:
    """Preserve only a small descriptive/PDF-conformance XMP allow-list."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for description in root.iter():
        if local_name(description.tag) != "Description":
            continue
        for attr in list(description.attrib):
            qualified = (namespace_name(attr), local_name(attr))
            if (
                qualified != ("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "about")
                and qualified not in XMP_SAFE_PROPERTIES
            ):
                description.attrib.pop(attr, None)
        for child in list(description):
            if (namespace_name(child.tag), local_name(child.tag)) not in XMP_SAFE_PROPERTIES:
                description.remove(child)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _inspect_pdf(path: Path) -> InspectionResult:
    result = InspectionResult(path, "PDF", True)
    try:
        with fitz.open(path) as doc:
            result.encrypted = _pdf_is_encrypted(doc)
            if result.encrypted:
                result.warnings.append("PDF 已加密或需要密码，无法安全处理。")
                return result
            result.signed = _pdf_has_signatures(doc)
            if result.signed:
                result.warnings.append("检测到 PDF 数字签名；默认跳过。")
            metadata = doc.metadata or {}
            for key, value in metadata.items():
                text = display_value(value)
                if not text:
                    continue
                personal = key in PERSONAL_PDF_KEYS
                result.items.append(MetadataItem("PDF 属性", key, text, personal))
            try:
                id_kind, id_value = doc.xref_get_key(-1, "ID")
                if id_kind != "null" and id_value not in {"", "null"}:
                    result.items.append(MetadataItem("PDF 标识", "trailer ID", display_value(id_value), True))
            except Exception:
                pass
            info_xref = _pdf_info_xref(doc)
            if info_xref:
                for key in doc.xref_get_keys(info_xref):
                    if key in PDF_INFO_STANDARD_KEYS:
                        continue
                    kind, value = doc.xref_get_key(info_xref, key)
                    text = display_value(value)
                    if kind != "null" and text and text != "null":
                        result.items.append(MetadataItem("PDF 自定义属性", key, text, True))
            try:
                xml_text = doc.get_xml_metadata()
                if xml_text:
                    _inspect_pdf_xmp(xml_text, result)
            except Exception:
                pass
            for page_number, page in enumerate(doc, 1):
                try:
                    annotations = page.annots()
                    if not annotations:
                        continue
                    for annotation in annotations:
                        info = annotation.info or {}
                        for key in ("title", "creationDate", "modDate", "subject"):
                            value = display_value(info.get(key))
                            if value:
                                result.items.append(
                                    MetadataItem(
                                        "PDF 批注属性",
                                        f"第 {page_number} 页 {key}",
                                        value,
                                        key != "subject",
                                    )
                                )
                except Exception as exc:
                    result.warnings.append(f"第 {page_number} 页批注属性无法完整检测：{exc}")
            try:
                count = doc.embfile_count()
                if count:
                    result.warnings.append(f"PDF 含 {count} 个嵌入附件；附件不会递归清理。")
                    for index in range(count):
                        try:
                            info = doc.embfile_info(index)
                            label = display_value(
                                info.get("ufilename") or info.get("filename") or f"附件 {index + 1}"
                            )
                        except Exception:
                            label = f"附件 {index + 1}"
                        result.items.append(MetadataItem("PDF 嵌入附件", "附件需人工复核", label, True))
            except Exception:
                pass
    except Exception as exc:
        result.supported = False
        result.warnings.append(f"无法读取 PDF：{exc}")
    return result


def _inspect_image(path: Path) -> InspectionResult:
    result = InspectionResult(path, "图片", True)
    try:
        with Image.open(path) as img:
            if getattr(img, "is_animated", False):
                result.supported = False
                result.warnings.append("暂不处理动画图片。")
                return result
            exif = img.getexif()
            for tag_id, value in exif.items():
                name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if name in IMAGE_TECHNICAL_EXIF:
                    continue
                result.items.append(MetadataItem("EXIF", name, display_value(value), True))
            if "icc_profile" in img.info:
                profile = img.info.get("icc_profile") or b""
                result.items.append(
                    MetadataItem("图片颜色配置", "ICC profile", f"{len(profile)} 字节", False)
                )
            safe_keys = {
                "icc_profile", "dpi", "gamma", "transparency", "aspect",
                "jfif", "jfif_version", "jfif_unit", "jfif_density",
                "progressive", "progression", "loop", "background",
                "compression", "resolution",
            }
            for key, value in img.info.items():
                if key in safe_keys or key == "exif":
                    continue
                result.items.append(MetadataItem("图片文本属性", key, display_value(value), True))
            if "exif" in img.info and not exif:
                result.items.append(MetadataItem("EXIF", "原始 EXIF 块", "存在", True))
            if "icc_profile" in img.info:
                result.warnings.append("个人信息模式会保留 ICC 颜色配置；“全部属性”模式会移除。")
            result.warnings.append("图片清理会重新编码；原文件不会被覆盖。")
    except Exception as exc:
        result.supported = False
        result.warnings.append(f"无法读取图片：{exc}")
    return result


def inspect_file(path: str | Path) -> InspectionResult:
    source = Path(path).expanduser().resolve()
    suffix = source.suffix.lower()
    if suffix in OOXML_EXTENSIONS:
        return _inspect_ooxml(source)
    if suffix in ODF_EXTENSIONS:
        return _inspect_odf(source)
    if suffix in PDF_EXTENSIONS:
        return _inspect_pdf(source)
    if suffix in IMAGE_EXTENSIONS:
        return _inspect_image(source)
    return InspectionResult(source, "不支持", False, warnings=["该文件类型不在安全支持范围内。"])


def unique_output_path(source: Path, output_dir: Path | None = None, suffix: str = "_clean") -> Path:
    folder = output_dir.resolve() if output_dir else source.parent
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{source.stem}{suffix}{source.suffix}"
    index = 2
    while candidate.exists() or candidate.resolve() == source.resolve():
        candidate = folder / f"{source.stem}{suffix}_{index}{source.suffix}"
        index += 1
    return candidate


def _temporary_sibling(output: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{output.stem}.",
        suffix=f"{output.suffix}.tmp",
        dir=output.parent,
    )
    os.close(descriptor)
    return Path(name)


def _publish_without_overwrite(temp: Path, output: Path) -> None:
    if output.exists():
        raise MetadataCleanError(f"输出文件已存在，未覆盖：{output.name}")
    # On Windows os.rename does not replace an existing destination.
    os.rename(temp, output)


def _remove_root_relationships(data: bytes, relation_endings: set[str]) -> bytes:
    root = _xml_root(data)
    for rel in list(root):
        rel_type = rel.attrib.get("Type", "").lower()
        if any(rel_type.endswith(ending) for ending in relation_endings):
            root.remove(rel)
    # OPC readers in Microsoft Office expect these package-control parts to
    # use their conventional default namespace, not a generated rel: prefix.
    return _serialize_with_default_namespace(root)


def _remove_content_type_overrides(data: bytes, part_names: set[str]) -> bytes:
    root = _xml_root(data)
    lowered = {name.lower() for name in part_names}
    for child in list(root):
        part_name = child.attrib.get("PartName", "").lower()
        if part_name in lowered:
            root.remove(child)
    return _serialize_with_default_namespace(root)


def _clear_core_properties(data: bytes, mode: CleanMode) -> bytes:
    root = _xml_root(data)
    targets = CORE_PERSONAL | (CORE_DESCRIPTIVE if mode == CleanMode.ALL else set())
    for child in list(root):
        if local_name(child.tag) in targets:
            # A typed empty dcterms:created / dcterms:modified element is not
            # a valid W3CDTF value and makes Microsoft Word request a repair.
            # These OOXML properties are optional, so remove the node itself.
            root.remove(child)
    return _serialize(root)


def _clear_app_properties(data: bytes) -> bytes:
    root = _xml_root(data)
    for child in list(root):
        if local_name(child.tag) in APP_PERSONAL:
            root.remove(child)
    return _serialize_with_default_namespace(root)


def _neutral_review_id(original: str, index: int) -> str:
    compact = f"{index:032x}"
    value = f"{compact[:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:]}"
    return "{" + value + "}" if original.startswith("{") and original.endswith("}") else value


def _collect_review_person_ids(zf: ZipFile) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in zf.namelist():
        low = name.casefold()
        if not low.endswith(".xml") or not any(token in low for token in ("people", "person")):
            continue
        try:
            root = _xml_root(zf.read(name))
        except ET.ParseError:
            continue
        for elem in root.iter():
            if local_name(elem.tag) != "person":
                continue
            for attr, raw_value in elem.attrib.items():
                if local_name(attr) == "id" and raw_value and raw_value not in mapping:
                    mapping[raw_value] = _neutral_review_id(raw_value, len(mapping) + 1)
    return mapping


def _anonymize_review_xml(data: bytes, person_ids: dict[str, str] | None = None) -> bytes:
    try:
        root = _xml_root(data)
    except ET.ParseError:
        return data
    changed = False
    for elem in root.iter():
        lname = local_name(elem.tag)
        if lname == "author" and elem.text:
            elem.text = "Anonymous"
            changed = True
        if lname not in REVIEW_ELEMENTS:
            continue
        for attr in list(elem.attrib):
            aname = local_name(attr)
            if lname == "person" and aname == "id":
                original = elem.attrib[attr]
                elem.attrib[attr] = (person_ids or {}).get(original, _neutral_review_id(original, 0))
                changed = True
                continue
            if lname == "threadedComment" and aname == "personId":
                original = elem.attrib[attr]
                elem.attrib[attr] = (person_ids or {}).get(original, _neutral_review_id(original, 0))
                changed = True
                continue
            if aname not in REVIEW_ATTRS:
                continue
            if aname in {"author", "displayName", "name"}:
                elem.attrib[attr] = "Anonymous"
            else:
                # Initials, dates, e-mail addresses and provider/user IDs are
                # optional review metadata.  Removing the attributes avoids
                # leaving a synthetic value that the verifier would still
                # (correctly) identify as review metadata.
                elem.attrib.pop(attr, None)
            changed = True
    return _serialize_preserving_namespaces(root, data) if changed else data


def _validate_ooxml_package(zf: ZipFile, options: CleanOptions) -> None:
    """Validate privacy invariants and reject semantically invalid dates."""
    names = set(zf.namelist())
    bad = zf.testzip()
    if bad:
        raise MetadataCleanError(f"输出包校验失败：{bad}")
    if "[Content_Types].xml" not in names:
        raise MetadataCleanError("输出包缺少 [Content_Types].xml。")
    content_types_data = zf.read("[Content_Types].xml")
    content_types_root = _xml_root(content_types_data)
    if local_name(content_types_root.tag) != "Types" or _serialized_root_qname(content_types_data) != b"Types":
        raise MetadataCleanError("[Content_Types].xml 未使用 Office 兼容的默认命名空间。")
    if "_rels/.rels" in names:
        relationships_data = zf.read("_rels/.rels")
        relationships_root = _xml_root(relationships_data)
        if local_name(relationships_root.tag) != "Relationships" or _serialized_root_qname(relationships_data) != b"Relationships":
            raise MetadataCleanError("根关系文件未使用 Office 兼容的默认命名空间。")
    if "docProps/custom.xml" in names:
        raise MetadataCleanError("输出包仍含自定义属性。")
    if options.remove_thumbnail and any(name.lower().startswith("docprops/thumbnail.") for name in names):
        raise MetadataCleanError("输出包仍含 Office 缩略图。")

    if options.mode == CleanMode.ALL:
        if {"docProps/core.xml", "docProps/app.xml"} & names:
            raise MetadataCleanError("全部属性模式仍残留 Office 属性部件。")
        return

    if "docProps/core.xml" in names:
        core = _xml_root(zf.read("docProps/core.xml"))
        residual = {local_name(elem.tag) for elem in core if local_name(elem.tag) in CORE_PERSONAL}
        if residual:
            raise MetadataCleanError(f"核心个人属性未完全移除：{', '.join(sorted(residual))}")
        for elem in core.iter():
            typed_as = next(
                (value for attr, value in elem.attrib.items() if local_name(attr) == "type"),
                "",
            )
            if typed_as.endswith("W3CDTF") and not (elem.text or "").strip():
                raise MetadataCleanError("检测到空的 W3CDTF 日期；已拒绝发布不兼容的 Office 副本。")

    if "docProps/app.xml" in names:
        app_data = zf.read("docProps/app.xml")
        app = _xml_root(app_data)
        if local_name(app.tag) != "Properties" or _serialized_root_qname(app_data) != b"Properties":
            raise MetadataCleanError("扩展属性文件未使用 Office 兼容的默认命名空间。")
        residual = {local_name(elem.tag) for elem in app if local_name(elem.tag) in APP_PERSONAL}
        if residual:
            raise MetadataCleanError(f"扩展个人属性未完全移除：{', '.join(sorted(residual))}")


def _clean_ooxml(source: Path, output: Path, options: CleanOptions) -> None:
    with ZipFile(source, "r") as zin:
        names = set(zin.namelist())
        related = _root_relationship_parts(zin)
        review_person_ids = _collect_review_person_ids(zin) if options.anonymize_reviewers else {}
        if _zip_is_signed(names):
            raise SignedFileError("检测到 Office 数字签名，已跳过以避免产生无效签名。")

        custom_parts = ({"docProps/custom.xml"} | related["custom-properties"]) & names
        core_parts = ({"docProps/core.xml"} | related["core-properties"]) & names
        app_parts = ({"docProps/app.xml"} | related["extended-properties"]) & names
        remove_parts = set(custom_parts)
        rel_endings = {"/custom-properties"}
        content_parts = {"/" + name for name in custom_parts}
        if options.remove_thumbnail:
            thumbnails = {
                name for name in names if name.lower().startswith("docprops/thumbnail.")
            } | (related["thumbnail"] & names)
            for name in thumbnails:
                remove_parts.add(name)
                content_parts.add("/" + name)
            rel_endings.add("/thumbnail")
        if options.mode == CleanMode.ALL:
            remove_parts.update(core_parts | app_parts)
            content_parts.update("/" + name for name in core_parts | app_parts)
            rel_endings.update({"/core-properties", "/extended-properties"})

        temp = _temporary_sibling(output)
        try:
            with ZipFile(temp, "w", compression=ZIP_DEFLATED) as zout:
                for info in zin.infolist():
                    name = info.filename
                    if name in remove_parts:
                        continue
                    data = zin.read(name)
                    if name == "_rels/.rels":
                        data = _remove_root_relationships(data, rel_endings)
                    elif name == "[Content_Types].xml":
                        data = _remove_content_type_overrides(data, content_parts)
                    elif options.mode == CleanMode.PERSONAL and name in core_parts:
                        data = _clear_core_properties(data, options.mode)
                    elif options.mode == CleanMode.PERSONAL and name in app_parts:
                        data = _clear_app_properties(data)
                    elif options.anonymize_reviewers and name.startswith(("word/", "xl/", "ppt/")) and name.endswith(".xml"):
                        # Review markup can occur in the main story, headers,
                        # footers, footnotes, endnotes and revision parts.
                        data = _anonymize_review_xml(data, review_person_ids)
                    zout.writestr(_clone_zip_info(info), data)
            with ZipFile(temp) as check:
                _validate_ooxml_package(check, options)
            _publish_without_overwrite(temp, output)
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)


def _clean_odf_meta(data: bytes, mode: CleanMode) -> bytes:
    root = _xml_root(data)
    targets = ODF_META_PERSONAL | (ODF_META_DESCRIPTIVE if mode == CleanMode.ALL else set())
    for parent in root.iter():
        for child in list(parent):
            if local_name(child.tag) in targets:
                parent.remove(child)
    return _serialize(root)


def _clean_odf_content(data: bytes) -> bytes:
    root = _xml_root(data)
    changed = False

    def visit(elem: ET.Element, in_review: bool = False) -> None:
        nonlocal changed
        current_review = in_review or local_name(elem.tag) in ODF_REVIEW_CONTAINERS
        if (
            current_review
            and namespace_name(elem.tag) == NS["dc_odf"]
            and local_name(elem.tag) in {"creator", "date"}
            and elem.text
        ):
            elem.text = None
            changed = True
        for child in elem:
            visit(child, current_review)

    visit(root)
    return _serialize(root) if changed else data


def _clean_odf(source: Path, output: Path, options: CleanOptions) -> None:
    with ZipFile(source, "r") as zin:
        names = set(zin.namelist())
        if _odf_is_encrypted(zin):
            raise EncryptedFileError("检测到 OpenDocument 加密成员，已跳过。")
        if _zip_is_signed(names):
            raise SignedFileError("检测到 OpenDocument 数字签名，已跳过。")
        temp = _temporary_sibling(output)
        try:
            with ZipFile(temp, "w", compression=ZIP_DEFLATED) as zout:
                for info in zin.infolist():
                    data = zin.read(info.filename)
                    if info.filename == "meta.xml":
                        data = _clean_odf_meta(data, options.mode)
                    elif options.anonymize_reviewers and info.filename == "content.xml":
                        data = _clean_odf_content(data)
                    zout.writestr(_clone_zip_info(info), data)
            with ZipFile(temp) as check:
                bad = check.testzip()
                if bad:
                    raise MetadataCleanError(f"输出包校验失败：{bad}")
            _publish_without_overwrite(temp, output)
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)


def _clean_pdf(source: Path, output: Path, options: CleanOptions) -> None:
    temp = _temporary_sibling(output)
    try:
        with fitz.open(source) as doc:
            if _pdf_is_encrypted(doc):
                raise EncryptedFileError("PDF 已加密或需要密码，已跳过。")
            if _pdf_has_signatures(doc):
                raise SignedFileError("检测到 PDF 数字签名，已跳过以避免签名失效。")
            old = doc.metadata or {}
            keys = ALL_PDF_KEYS if options.mode == CleanMode.ALL else PERSONAL_PDF_KEYS
            new_meta = {key: value for key, value in old.items() if key not in keys}
            for key in keys:
                if key in old:
                    new_meta[key] = ""
            doc.set_metadata(new_meta)

            # Non-standard /Info keys are treated as potentially personal custom
            # properties in both modes.  Standard keys follow the selected mode.
            info_xref = _pdf_info_xref(doc)
            if info_xref:
                standard_targets = PDF_INFO_STANDARD_KEYS if options.mode == CleanMode.ALL else PDF_INFO_PERSONAL_KEYS
                for key in doc.xref_get_keys(info_xref):
                    if key not in PDF_INFO_STANDARD_KEYS or key in standard_targets:
                        try:
                            doc.xref_set_key(info_xref, key, "null")
                        except Exception:
                            pass

            try:
                xml_text = doc.get_xml_metadata()
                if xml_text:
                    if options.mode == CleanMode.ALL:
                        doc.del_xml_metadata()
                    else:
                        sanitized = _sanitize_xmp_personal(xml_text)
                        if sanitized is None:
                            doc.del_xml_metadata()
                        else:
                            doc.set_xml_metadata(sanitized)
            except Exception:
                # If an unreadable XMP packet cannot be safely edited, remove it.
                try:
                    doc.del_xml_metadata()
                except Exception:
                    pass

            # Keep annotation content and geometry, but clear identity/history
            # fields.  Subject is descriptive and is only removed in ALL mode.
            if options.anonymize_reviewers:
                for page in doc:
                    annotation = page.first_annot
                    while annotation:
                        next_annotation = annotation.next
                        for key in ("T", "CreationDate", "M"):
                            doc.xref_set_key(annotation.xref, key, "null")
                        if options.mode == CleanMode.ALL:
                            doc.xref_set_key(annotation.xref, "Subj", "null")
                        annotation = next_annotation
            try:
                doc.xref_set_key(-1, "ID", "null")
            except Exception:
                pass
            doc.save(temp, garbage=4, deflate=True, clean=True, no_new_id=True)
        _publish_without_overwrite(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def _clean_image(source: Path, output: Path, options: CleanOptions) -> None:
    temp = _temporary_sibling(output)
    try:
        with Image.open(source) as original:
            if getattr(original, "is_animated", False):
                raise MetadataCleanError("暂不处理动画图片。")
            safe_keys = {"transparency"}
            if options.mode == CleanMode.PERSONAL:
                safe_keys.update({"icc_profile", "dpi", "gamma"})
            safe = {key: original.info[key] for key in safe_keys if key in original.info}
            image = ImageOps.exif_transpose(original)
            # Pillow copies ``original.info`` onto the transposed image and may
            # write those chunks implicitly. Re-add only explicitly approved
            # rendering fields through save kwargs below.
            image.info.clear()
            suffix = source.suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                kwargs: dict[str, object] = {"quality": 95, "optimize": True}
                try:
                    sampling = JpegImagePlugin.get_sampling(original)
                    if sampling >= 0:
                        kwargs["subsampling"] = sampling
                except Exception:
                    pass
                if "icc_profile" in safe:
                    kwargs["icc_profile"] = safe["icc_profile"]
                image.save(temp, format="JPEG", **kwargs)
            elif suffix == ".png":
                image.save(temp, format="PNG", optimize=True, **safe)
            elif suffix in {".tif", ".tiff"}:
                compression = original.info.get("compression", "tiff_deflate")
                image.save(temp, format="TIFF", compression=compression, **safe)
            elif suffix == ".webp":
                image.save(temp, format="WEBP", lossless=True, method=6, **safe)
            else:
                raise MetadataCleanError("不支持的图片格式。")
        _publish_without_overwrite(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def clean_file(
    path: str | Path,
    output_dir: str | Path | None = None,
    options: CleanOptions | None = None,
) -> CleanResult:
    try:
        source = Path(path).expanduser().resolve()
    except Exception as exc:
        source = Path(str(path))
        return CleanResult(source, None, False, error=f"无法解析文件路径：{exc}")
    opts = options or CleanOptions()
    try:
        before = inspect_file(source)
    except Exception as exc:
        return CleanResult(source, None, False, error=f"无法检测文件：{exc}")
    if not before.supported:
        return CleanResult(source, None, False, warnings=before.warnings, error="不支持或无法读取该文件。")
    if before.encrypted:
        return CleanResult(source, None, False, warnings=before.warnings, error="文件已加密。")
    if before.signed:
        return CleanResult(source, None, False, warnings=before.warnings, error="数字签名文件已跳过。")

    try:
        out_dir = Path(output_dir).expanduser().resolve() if output_dir else None
        output = unique_output_path(source, out_dir)
    except Exception as exc:
        return CleanResult(source, None, False, warnings=before.warnings, error=f"无法创建输出路径：{exc}")

    try:
        suffix = source.suffix.lower()
        if suffix in OOXML_EXTENSIONS:
            _clean_ooxml(source, output, opts)
        elif suffix in ODF_EXTENSIONS:
            _clean_odf(source, output, opts)
        elif suffix in PDF_EXTENSIONS:
            _clean_pdf(source, output, opts)
        elif suffix in IMAGE_EXTENSIONS:
            _clean_image(source, output, opts)
        else:
            raise MetadataCleanError("该文件类型不在安全支持范围内。")
    except Exception as exc:
        return CleanResult(source, None, False, warnings=before.warnings, error=str(exc))

    def requested(items: list[MetadataItem]) -> list[MetadataItem]:
        selected: list[MetadataItem] = []
        reviewer_groups = {"审阅信息", "OpenDocument 审阅信息", "PDF 批注属性"}
        for item in items:
            if item.group == "预览" and not opts.remove_thumbnail:
                continue
            if item.group in reviewer_groups and not opts.anonymize_reviewers:
                continue
            if opts.mode == CleanMode.PERSONAL:
                if item.personal:
                    selected.append(item)
            elif not (item.group == "PDF 属性" and item.name in {"format", "encryption"}):
                selected.append(item)
        return selected

    targets_before = requested(before.items)
    residual: list[MetadataItem] = []
    warnings = list(before.warnings)
    if opts.verify_after_clean:
        try:
            after = inspect_file(output)
        except Exception as exc:
            return CleanResult(
                source,
                output,
                False,
                warnings=warnings,
                error=f"副本已生成，但清理后复检失败：{exc}",
            )
        warnings.extend(w for w in after.warnings if w not in warnings)
        if not after.supported:
            return CleanResult(
                source,
                output,
                False,
                warnings=warnings,
                error="副本已生成，但清理后无法重新读取；请勿直接对外发送。",
            )
        residual = requested(after.items)
    removed = max(0, len(targets_before) - len(residual))
    error = "" if not residual else "副本已生成，但复检仍发现所选范围内的元数据。"
    return CleanResult(source, output, not residual, removed, residual, warnings, error)
