import json
import sys
from pathlib import Path

def get_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

ROOT = get_root()
# 按用户确认的 NAPS2 便携版结构：exe、app、data 同级。
APP_DIR = ROOT / "app"
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
PROFILE_FILE = DATA_DIR / "profiles.xml"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
NAPS2_CONSOLE = APP_DIR / "NAPS2.Console.exe"
NAPS2_GUI = ROOT / "naps2.exe"
DEFAULTS = {
    "profile": "", "threshold": 245, "margin_mm": 8,
    "gap_mm": 8, "arrangement": "左右排列"
}

def ensure_runtime_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # 程序异常中断后，清理上次遗留的临时文件；只处理 output。
    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_settings():
    ensure_runtime_dirs()
    data = DEFAULTS.copy()
    if SETTINGS_FILE.is_file():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for key in DEFAULTS:
                    if key in saved:
                        data[key] = saved[key]
        except (OSError, ValueError, TypeError):
            pass
    return data

def save_settings(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    safe = DEFAULTS.copy()
    for key in DEFAULTS:
        if key in data:
            safe[key] = data[key]
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_FILE)
