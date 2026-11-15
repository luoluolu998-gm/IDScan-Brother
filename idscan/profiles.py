"""只读读取随 IDScan 提供的 data/profiles.xml。"""
from pathlib import Path
import xml.etree.ElementTree as ET


def _child_text(node, name):
    # 同时兼容普通 XML 和带默认 namespace 的 XML。
    child = node.find(name)
    if child is None:
        child = node.find(f"{{*}}{name}")
    return (child.text or "").strip() if child is not None else ""


def read_profiles(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"找不到扫描配置文件：{path}\n请确认 data\\profiles.xml 存在。")
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValueError(f"无法读取 profiles.xml：{exc}") from exc

    result = []
    for node in root.iter():
        if node.tag.split("}")[-1] != "ScanProfile":
            continue
        display = _child_text(node, "DisplayName")
        device = next((c for c in node if c.tag.split("}")[-1] == "Device"), None)
        device_name = _child_text(device, "Name") if device is not None else ""
        device_id = _child_text(device, "ID") if device is not None else ""
        if not display:
            display = device_name
        if not display:
            continue
        result.append({
            "display_name": display,
            "device_name": device_name,
            "device_id": device_id,
            "is_default": _child_text(node, "IsDefault").lower() == "true",
        })
    return result


def choose_default(profiles):
    if not profiles:
        return ""
    return next((p["display_name"] for p in profiles if p["is_default"]), profiles[0]["display_name"])
