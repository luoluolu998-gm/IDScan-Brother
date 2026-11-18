import os
import subprocess
from pathlib import Path


def scan_to_image(console_path, profile, output_path, working_dir=None):
    """调用 NAPS2 扫描仪，将扫描结果保存为图片。"""

    console = Path(console_path)

    if not console.is_file():
        raise FileNotFoundError(
            "找不到 NAPS2.Console.exe，请检查 app 文件夹。"
        )

    if not profile:
        raise ValueError("没有选择 NAPS2 扫描配置。")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output_path.unlink()

    cmd = [
        str(console.resolve()),
        "-p", profile,
        "-o", str(output_path.resolve())
    ]

    no_window = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if os.name == "nt" else 0
    )

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=no_window,
        cwd=(
            str(Path(working_dir).resolve())
            if working_dir else None
        )
    )

    if result.returncode != 0 or not output_path.is_file():

        detail = (
            (result.stdout or "") + "\n" +
            (result.stderr or "")
        ).strip()

        raise RuntimeError(
            "NAPS2 扫描失败。\n\n" + detail[-5000:]
        )

    return output_path


def deskew_image(console_path, input_path, output_path, working_dir=None):
    """
    调用 NAPS2 对单张图片进行自动倾斜校正。

    使用 --deskew 参数。
    原始图片不会被覆盖，校正结果保存到新的文件。
    """

    console = Path(console_path)
    source = Path(input_path)
    target = Path(output_path)

    if not console.is_file():
        raise FileNotFoundError(
            f"找不到 NAPS2.Console.exe：{console}"
        )

    if not source.is_file():
        raise FileNotFoundError(
            f"找不到待校正图片：{source}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)

    # 删除同名旧校正文件，避免误读上一次的结果
    if target.exists():
        target.unlink()

    cmd = [
        str(console.resolve()),
        "-i", str(source.resolve()),
        "-n", "0",
        "-o", str(target.resolve()),
        "--deskew",
        "-f"
    ]

    no_window = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if os.name == "nt" else 0
    )

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=no_window,
        cwd=(
            str(Path(working_dir).resolve())
            if working_dir else None
        )
    )

    if result.returncode != 0 or not target.is_file():

        detail = (
            (result.stdout or "") + "\n" +
            (result.stderr or "")
        ).strip()

        raise RuntimeError(
            "NAPS2 自动校正失败。\n\n" + detail[-5000:]
        )

    return target


def launch_naps2(gui_path, working_dir=None):
    """启动 NAPS2 图形界面。"""

    gui = Path(gui_path)

    if not gui.is_file():
        raise FileNotFoundError(
            f"找不到 NAPS2 程序：{gui}"
        )

    subprocess.Popen(
        [str(gui.resolve())],
        cwd=(
            str(Path(working_dir).resolve())
            if working_dir else None
        )
    )