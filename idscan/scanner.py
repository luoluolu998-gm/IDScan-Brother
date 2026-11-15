"""NAPS2 调用模块：保留 2.0 已验证的命令参数。"""
import os
import subprocess
from pathlib import Path

def scan_to_image(console_path, profile, output_path, working_dir=None):
    console = Path(console_path)
    if not console.is_file():
        raise FileNotFoundError("找不到 NAPS2.Console.exe，请检查 app 文件夹。")
    if not profile:
        raise ValueError("没有选择 NAPS2 扫描配置。")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    # 与 2.0 完全一致的 NAPS2 命令参数：-p Profile名称 -o 输出文件。
    cmd = [str(console.resolve()), "-p", profile, "-o", str(output_path.resolve())]
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", creationflags=no_window,
                            cwd=str(Path(working_dir).resolve()) if working_dir else None)
    if result.returncode != 0 or not output_path.exists():
        detail = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        raise RuntimeError("NAPS2 扫描失败。\n\n" + detail[-5000:])
    return output_path

def launch_naps2(gui_path, working_dir=None):
    path = Path(gui_path)
    if not path.is_file():
        raise FileNotFoundError(f"找不到 NAPS2 主程序：{path}\n请确认 naps2.exe 与小程序位于同一目录。")
    if os.name == "nt":
        os.startfile(str(path), "open")
    else:
        subprocess.Popen([str(path)], cwd=str(working_dir) if working_dir else None)
