from __future__ import annotations

import base64
from xml.etree import ElementTree as ET

from .exceptions import XmlEntryNotFound


def extract_mapping_blob(tsi_path: str) -> bytes:
    """
    Extracts and base64-decodes the controller mapping blob from a .tsi file.

    Looks for <Entry Name="DeviceIO.Config.Controller" Type="3" Value="..."/>.
    """
    with open(tsi_path, "rb") as f:
        text = f.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(text)
    for e in root.findall(".//Entry"):
        if e.attrib.get("Name") == "DeviceIO.Config.Controller":
            b64 = e.attrib.get("Value", "")
            return base64.b64decode(b64)
    raise XmlEntryNotFound("DeviceIO.Config.Controller not found in TSI XML.")
