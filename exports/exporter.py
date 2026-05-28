# exports/exporter.py
import json
import csv
import xml.etree.ElementTree as ET
from typing import List
from models.scraped_item import ScrapedItem, FailedURL
from utils.logger import get_logger

log = get_logger("exporter")


def _to_dict(item: ScrapedItem) -> dict:
    return {k: str(v) if v is not None else "" for k, v in item.model_dump().items()}


def save_json(data: List[ScrapedItem], path: str = "result.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([_to_dict(i) for i in data], f, ensure_ascii=False, indent=2)
    log.info(f"Saved JSON → {path} ({len(data)} records)")


def save_csv(data: List[ScrapedItem], path: str = "result.csv"):
    if not data:
        return
    rows = [_to_dict(i) for i in data]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"Saved CSV  → {path} ({len(data)} records)")


def save_xml(data: List[ScrapedItem], path: str = "result.xml"):
    root = ET.Element("items")
    for item in data:
        el = ET.SubElement(root, "item")
        for k, v in _to_dict(item).items():
            child = ET.SubElement(el, k)
            child.text = v
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    log.info(f"Saved XML  → {path} ({len(data)} records)")


def save_failures(failures: List[FailedURL], path: str = "failed_urls.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([f.model_dump() for f in failures], f, ensure_ascii=False, indent=2, default=str)
    log.info(f"Saved failures → {path} ({len(failures)} entries)")
