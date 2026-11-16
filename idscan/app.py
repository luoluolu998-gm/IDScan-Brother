import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .settings import (
    ROOT, APP_DIR, CONFIG_DIR, DATA_DIR, OUTPUT_DIR, PROFILE_FILE,
    NAPS2_CONSOLE, NAPS2_GUI, load_settings, save_settings,
)
from .profiles import read_profiles, choose_default
from .scanner import scan_to_image, launch_naps2
from .imaging import load_and_trim
from .a4_correct import correct_a4
from .layout import compose_a4
from .exporter import save_output
from .preview import fit_preview


class IDScanApp:

    def __init__(self, root):
        self.root = root

        self.root.title("IDScan Brother 3.0")
        self.root.geometry("1000x680")
        self.root.resizable(False, False)
        self.root.configure(bg="#edf3fb")

        self.settings = load_settings()
        self.profiles = []

        self.front = None
        self.back = None

        self.front_raw = None
        self.back_raw = None

        self.front_dpi = (300, 300)
        self.back_dpi = (300, 300)

        self.single_raw = None
        self.single_corrected = None

        # 单面预览状态：False=原图，True=校正图
        self.single_show_corrected = False

        self.latest_raw = None
        self.latest_corrected = None

        self.current_mode = "duplex"
        self.busy = False

        self._preview_images = []
        self.preview_labels = []
        self.preview_title_labels = []
        self.action_buttons = []

        self._startup_error = ""

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self._load_profiles()
        self._build_ui()
        self._refresh_previews()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ==================================================
    # 扫描配置
    # ==================================================

    def _load_profiles(self):
        try:
            self.profiles = read_profiles(PROFILE_FILE)

            names = [
                p["display_name"] for p in self.profiles
            ]

            current = self.settings.get("profile", "")

            if current not in names:
                self.settings["profile"] = choose_default(
                    self.profiles
                )

        except Exception as exc:
            self.profiles = []
            self._startup_error = str(exc)

        save_settings(self.settings)

    def _naps2_ready(self):
        return NAPS2_CONSOLE.is_file() and bool(self.profiles)

    def _profile_changed(self, value):
        self.settings["profile"] = value
        save_settings(self.settings)

        self._update_device_status()

    def _update_device_status(self):
        if self._naps2_ready():
            self.status_dot.configure(
                text="● 扫描配置已就绪",
                fg="#15945D"
            )
        else:
            self.status_dot.configure(
                text="● 扫描配置未就绪",
                fg="#C17A25"
            )

    # ==================================================
    # 主界面
    # ==================================================

    def _build_ui(self):

        self.build_brand_bar()

        body = tk.Frame(
            self.root,
            bg=self.bg
        )
        body.pack(
            fill="both",
            expand=True
        )

        self.build_sidebar(body)

        workspace = tk.Frame(
            body,
            bg=self.bg
        )
        workspace.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(12, 8),
            pady=10
        )

        self.workspace = workspace

        self.build_workspace_header(workspace)
        self.build_preview_area(workspace)
        self.build_bottom_area(workspace)
        self.build_status_bar(workspace)

    # ==================================================
    # 颜色
    # ==================================================

    @property
    def bg(self):
        return "#edf3fb"

    @property
    def blue(self):
        return "#1260b5"

    # ==================================================
    # 顶部品牌栏
    # ==================================================

    def build_brand_bar(self):

        bar = tk.Frame(
            self.root,
            bg=self.blue,
            height=52
        )

        bar.pack(
            side="top",
            fill="x"
        )

        bar.pack_propagate(False)

        tk.Label(
            bar,
            text="▣  IDScan Brother 3.0",
            font=("Microsoft YaHei UI", 15, "bold"),
            bg=self.blue,
            fg="white"
        ).pack(
            side="left",
            padx=(18, 12)
        )

        tk.Label(
            bar,
            text="证件扫描  ·  智能校正  ·  A4 专业输出",
            font=("Microsoft YaHei UI", 10),
            bg=self.blue,
            fg="#e5efff"
        ).pack(
            side="left"
        )

    # ==================================================
    # 左侧导航
    # ==================================================

    def build_sidebar(self, parent):

        sidebar = tk.Frame(
            parent,
            bg="#f7faff",
            width=135
        )

        sidebar.pack(
            side="left",
            fill="y"
        )

        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="IDSCAN",
            font=("Arial", 9, "bold"),
            bg="#f7faff",
            fg="#7890ae"
        ).pack(pady=(22, 14))

        self.create_nav_item(
            sidebar, "⌂", "主页",
            self.show_home, True
        )

        self.create_nav_item(
            sidebar, "⚙", "设置",
            self.open_settings
        )

        self.create_nav_item(
            sidebar, "▣", "NAPS2",
            self.open_naps2
        )

        self.create_nav_item(
            sidebar, "ⓘ", "关于",
            self.show_about
        )

        tk.Frame(
            sidebar,
            bg="#e4ebf5",
            height=1
        ).pack(
            fill="x",
            padx=15,
            pady=8
        )

        spacer = tk.Frame(
            sidebar,
            bg="#f7faff"
        )

        spacer.pack(
            fill="both",
            expand=True
        )

        tk.Label(
            sidebar,
            text="VERSION\n3.0",
            font=("Arial", 8, "bold"),
            bg="#f7faff",
            fg="#a2b2c7",
            justify="center"
        ).pack(
            side="bottom",
            pady=15
        )

    def create_nav_item(
        self,
        parent,
        symbol,
        text,
        command,
        active=False
    ):

        bg = "#e2efff" if active else "#f7faff"
        fg = self.blue if active else "#405875"

        item = tk.Frame(
            parent,
            bg=bg,
            height=70
        )

        item.pack(
            fill="x",
            padx=6,
            pady=3
        )

        item.pack_propagate(False)

        btn = tk.Button(
            item,
            text=f"{symbol}\n{text}",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=bg,
            fg=fg,
            activebackground="#d8e9ff",
            activeforeground=self.blue,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=command
        )

        btn.pack(
            fill="both",
            expand=True
        )

    # ==================================================
    # 工作区顶部
    # ==================================================

    def build_workspace_header(self, parent):

        header = tk.Frame(
            parent,
            bg=self.bg,
            height=48
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(False)

        tk.Label(
            header,
            text="证件扫描工作台",
            font=("Microsoft YaHei UI", 16, "bold"),
            bg=self.bg,
            fg="#233b5b"
        ).pack(
            side="left",
            padx=(0, 8)
        )

        right = tk.Frame(
            header,
            bg=self.bg
        )

        right.pack(
            side="right",
            fill="y"
        )

        tk.Label(
            right,
            text="扫描配置：",
            font=("Microsoft YaHei UI", 9),
            bg=self.bg,
            fg="#60758f"
        ).pack(
            side="left",
            pady=8
        )

        names = [
            p["display_name"] for p in self.profiles
        ] or ["未发现扫描配置"]

        current = self.settings.get("profile", "")

        if current not in names:
            current = names[0]

        self.profile_var = tk.StringVar(
            value=current
        )

        self.profile_menu = tk.OptionMenu(
            right,
            self.profile_var,
            *names,
            command=self._profile_changed
        )

        self.profile_menu.config(
            width=16,
            bg="white",
            fg="#18395e",
            activebackground="#e5efff",
            relief="flat",
            highlightthickness=0,
            font=("Microsoft YaHei UI", 9)
        )

        self.profile_menu["menu"].config(
            font=("Microsoft YaHei UI", 9)
        )

        self.profile_menu.pack(
            side="left",
            padx=(5, 12),
            pady=6
        )

        if not self.profiles:
            self.profile_menu.configure(
                state="disabled"
            )

        self.status_dot = tk.Label(
            right,
            text="",
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=self.bg
        )

        self.status_dot.pack(
            side="left",
            pady=8
        )

        self._update_device_status()

    # ==================================================
    # 五个预览框
    # ==================================================

    def build_preview_area(self, parent):

        area = tk.Frame(
            parent,
            bg=self.bg
        )

        area.pack(
            fill="both",
            expand=True,
            pady=(3, 8)
        )

        area.grid_columnconfigure(
            0, weight=1, uniform="cols"
        )

        area.grid_columnconfigure(
            1, weight=1, uniform="cols"
        )

        area.grid_columnconfigure(
            2, weight=2, uniform="cols"
        )

        area.grid_rowconfigure(
            0, weight=1, uniform="rows"
        )

        area.grid_rowconfigure(
            1, weight=1, uniform="rows"
        )

        # 第一列：正面原图、反面原图
        self.create_preview_card(
            area,
            "01  正面原始图",
            0, 0,
            "#1769c2"
        )

        self.create_preview_card(
            area,
            "02  反面原始图",
            1, 0,
            "#1769c2"
        )

        # 第二列：正面校正图、反面校正图
        self.create_preview_card(
            area,
            "03  正面校正图",
            0, 1,
            "#159b70"
        )

        self.create_preview_card(
            area,
            "04  反面校正图",
            1, 1,
            "#159b70"
        )

        # 第三列：A4 页面预览
        self.create_preview_card(
            area,
            "05  A4 页面预览",
            0, 2,
            "#6658c9",
            rowspan=2
        )

    def create_preview_card(
        self,
        parent,
        title,
        row,
        column,
        color,
        rowspan=1
    ):

        card = tk.Frame(
            parent,
            bg="white",
            highlightthickness=1,
            highlightbackground="#e3eaf3"
        )

        card.grid(
            row=row,
            column=column,
            rowspan=rowspan,
            sticky="nsew",
            padx=4,
            pady=4
        )

        card.grid_columnconfigure(
            0, weight=1
        )

        card.grid_rowconfigure(
            1, weight=1
        )

        titlebar = tk.Frame(
            card,
            bg=color,
            height=30
        )

        titlebar.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=6,
            pady=(6, 4)
        )

        titlebar.grid_propagate(False)

        title_label = tk.Label(
            titlebar,
            text=title,
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=color,
            fg="white"
        )

        title_label.pack(
            side="left",
            padx=8
        )

        preview = tk.Label(
            card,
            text="等待图像",
            font=("Microsoft YaHei UI", 9),
            bg="#eef2f8",
            fg="#9aa9ba",
            compound="center"
        )

        preview.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=7,
            pady=5
        )

        self.preview_labels.append(preview)
        self.preview_title_labels.append(title_label)

    # ==================================================
    # 底部操作区
    # ==================================================

    def build_bottom_area(self, parent):

        bottom = tk.Frame(
            parent,
            bg=self.bg,
            height=160
        )

        bottom.pack(
            fill="x"
        )

        bottom.pack_propagate(False)

        # 左侧扫描和图像处理区域
        process = tk.Frame(
            bottom,
            bg="white",
            highlightthickness=1,
            highlightbackground="#e3eaf3"
        )

        process.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 5)
        )

        tk.Label(
            process,
            text="扫描与图像处理",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg="white",
            fg="#284363"
        ).pack(
            anchor="w",
            padx=11,
            pady=(4, 1)
        )

        # 第一行：扫描按钮
        scan_row = tk.Frame(
            process,
            bg="white"
        )

        scan_row.pack(
            fill="x",
            padx=6,
            pady=1
        )

        self.create_action_button(
            scan_row,
            "▣ 扫描正面",
            "#1769c2",
            "white",
            lambda: self.start_scan("front")
        )

        self.create_action_button(
            scan_row,
            "▣ 扫描反面",
            "#1769c2",
            "white",
            lambda: self.start_scan("back")
        )

        self.create_action_button(
            scan_row,
            "▤ 扫描单面",
            "#1769c2",
            "white",
            lambda: self.start_scan("single")
        )

        # 第二行：导入图片按钮
        import_row = tk.Frame(
            process,
            bg="white"
        )

        import_row.pack(
            fill="x",
            padx=6,
            pady=1
        )

        self.create_action_button(
            import_row,
            "＋ 导入正面图片",
            "#e5f0ff",
            "#1260b5",
            lambda: self.add_image("front")
        )

        self.create_action_button(
            import_row,
            "＋ 导入反面图片",
            "#e5f0ff",
            "#1260b5",
            lambda: self.add_image("back")
        )

        self.create_action_button(
            import_row,
            "＋ 导入单张图片",
            "#e5f0ff",
            "#1260b5",
            lambda: self.add_image("single")
        )

        # 第三行：排版和单面校正按钮
        layout_row = tk.Frame(
            process,
            bg="white"
        )

        layout_row.pack(
            fill="x",
            padx=6,
            pady=1
        )

        self.arrangement = tk.StringVar(
            value=self.settings.get(
                "arrangement",
                "左右排列"
            )
        )

        self.create_action_button(
            layout_row,
            "⇄ 左右排列",
            "#e6f0fd",
            "#1769c2",
            lambda: self.change_layout("左右排列")
        )

        self.create_action_button(
            layout_row,
            "⇵ 上下排列",
            "#e6f0fd",
            "#1769c2",
            lambda: self.change_layout("上下排列")
        )

        self.create_action_button(
            layout_row,
            "⌁ 单面校正",
            "#e6f0fd",
            "#1769c2",
            lambda: self.change_layout("单面校正")
        )

        tk.Label(
            process,
            text="扫描正反面后自动生成 A4 排版预览。",
            font=("Microsoft YaHei UI", 8),
            bg="white",
            fg="#8295ad"
        ).pack(
            anchor="w",
            padx=11,
            pady=(1, 1)
        )

        # 右侧文件输出区域，保持原样
        output = tk.Frame(
            bottom,
            bg="white",
            width=215,
            highlightthickness=1,
            highlightbackground="#e3eaf3"
        )

        output.pack(
            side="right",
            fill="y",
            padx=(5, 0)
        )

        output.pack_propagate(False)

        tk.Label(
            output,
            text="文件输出",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg="white",
            fg="#284363"
        ).pack(
            anchor="w",
            padx=11,
            pady=(7, 4)
        )

        self.export_jpg = self.create_action_button(
            output,
            "▧ 生成 JPG 图像",
            "#20a65f",
            "white",
            lambda: self.generate("JPG"),
            fill="x"
        )

        self.export_pdf = self.create_action_button(
            output,
            "▤ 生成 PDF 文件",
            "#6658c9",
            "white",
            lambda: self.generate("PDF"),
            fill="x"
        )

        tk.Label(
            output,
            text="A4 竖向 · 300 DPI",
            font=("Microsoft YaHei UI", 8),
            bg="white",
            fg="#8295ad"
        ).pack(pady=3)

    def create_action_button(
        self,
        parent,
        text,
        bg,
        fg,
        command,
        fill=None
    ):

        button = tk.Button(
            parent,
            text=text,
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=command,
            height=1
        )

        if fill == "x":
            button.pack(
                fill="x",
                padx=9,
                pady=3,
                ipady=4
            )
        else:
            button.pack(
                side="left",
                fill="x",
                expand=True,
                padx=3,
                pady=1,
                ipady=2
            )

        self.action_buttons.append(button)

        return button

    # ==================================================
    # 状态栏
    # ==================================================

    def build_status_bar(self, parent):

        self.status_text = tk.Label(
            parent,
            text="准备就绪",
            font=("Microsoft YaHei UI", 8),
            bg=self.bg,
            fg="#60758f",
            anchor="w"
        )

        self.status_text.pack(
            fill="x",
            pady=(5, 0)
        )

    def _set_status(self, text, busy=False):

        self.status_text.configure(
            text=text
        )

        self.busy = busy

        for button in self.action_buttons:
            button.configure(
                state="disabled" if busy else "normal"
            )

        self.profile_menu.configure(
            state=(
                "disabled"
                if busy or not self.profiles
                else "normal"
            )
        )

    # ==================================================
    # 扫描
    # ==================================================

    def start_scan(self, side):

        if self.busy:
            return

        if not NAPS2_CONSOLE.is_file():
            messagebox.showwarning(
                "NAPS2 程序缺失",
                f"找不到：\n{NAPS2_CONSOLE}\n\n"
                "请检查 NAPS2 程序目录。"
            )
            return

        profile = self.profile_var.get().strip()

        if not self.profiles or profile == "未发现扫描配置":
            messagebox.showwarning(
                "没有扫描配置",
                f"请检查：\n{PROFILE_FILE}"
            )
            return

        side_name = {
            "front": "正面",
            "back": "反面",
            "single": "单面"
        }[side]

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        output = OUTPUT_DIR / (
            f"scan_{side}_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
        )

        self._set_status(
            f"正在扫描{side_name}，请稍候……",
            True
        )

        def worker():
            try:
                scan_to_image(
                    NAPS2_CONSOLE,
                    profile,
                    output,
                    working_dir=ROOT
                )

                with Image.open(output) as source:
                    raw = source.convert("RGB").copy()

                if side in ("front", "back"):

                    processed, dx, dy = load_and_trim(
                        output,
                        self.settings["threshold"]
                    )

                    self.root.after(
                        0,
                        lambda: self._scan_done(
                            side,
                            raw,
                            processed,
                            dx,
                            dy
                        )
                    )

                else:

                    corrected, angle = correct_a4(raw)

                    self.root.after(
                        0,
                        lambda: self._single_done(
                            raw,
                            corrected,
                            angle
                        )
                    )

            except Exception as exc:
                error = str(exc)

                self.root.after(
                    0,
                    lambda e=error: self._scan_error(e)
                )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()

    def _scan_done(
        self,
        side,
        raw,
        processed,
        dx,
        dy
    ):

        if side == "front":
            self.front = processed
            self.front_dpi = (dx, dy)
            self.front_raw = raw.copy()
            label = "正面"

        else:
            self.back = processed
            self.back_dpi = (dx, dy)
            self.back_raw = raw.copy()
            label = "反面"

        self.latest_raw = raw
        self.latest_corrected = processed

        self.current_mode = "duplex"

        self._refresh_previews()

        self._set_status(
            f"{label}扫描、识别和校正完成"
        )

    def _single_done(
        self,
        raw,
        corrected,
        angle
    ):

        self.single_raw = raw
        self.single_corrected = corrected

        # 扫描完成后，先显示原始图片
        self.single_show_corrected = False

        self.latest_raw = raw
        self.latest_corrected = corrected

        self.current_mode = "single"

        self._refresh_previews()

        self._set_status(
            f"单面扫描完成；倾斜校正 {angle:.2f}°，当前显示原图"
        )

    def _scan_error(self, error):

        self._set_status("扫描失败")

        messagebox.showerror(
            "扫描错误",
            error
        )

    # ==================================================
    # 页面排列
    # ==================================================

    def change_layout(self, value):

        if value == "单面校正":

            if self.single_raw is None or self.single_corrected is None:
                messagebox.showinfo(
                    "单面校正",
                    "请先扫描或导入一张单面文件。"
                )
                return

            self.current_mode = "single"

            # 每点击一次，在原图和校正图之间切换
            self.single_show_corrected = not self.single_show_corrected

            self._refresh_previews()

            self._set_status(
                "当前显示：单面校正效果"
                if self.single_show_corrected
                else "当前显示：单面原始图片"
            )

            return

        else:

            self.arrangement.set(value)
            self.settings["arrangement"] = value
            self.current_mode = "duplex"

        save_settings(self.settings)

        self._refresh_previews()

        self._set_status(f"页面排列：{value}")

    # ==================================================
    # A4 页面合成
    # ==================================================

    def _build_page(self):

        if self.current_mode == "single":

            if self.single_corrected is None:
                raise ValueError("请先扫描或导入单面文件。")

            return self.single_corrected

        if self.front is None or self.back is None:
            raise ValueError(
                "请先扫描或导入正面和反面图片。"
            )

        return compose_a4(
            self.front,
            self.back,
            self.front_dpi,
            self.back_dpi,
            self.arrangement.get(),
            output_dpi=300,
            margin_mm=self.settings["margin_mm"],
            gap_mm=self.settings["gap_mm"],
        )

    # ==================================================
    # 五个预览框刷新
    # ==================================================

    def _refresh_previews(self):

        if not self.preview_labels:
            return

        # 先让 Tk 完成布局计算，确保读取到正确的预览框尺寸
        self.root.update_idletasks()

        if self.current_mode == "single":

            # 单面模式：前四个小框保持空白，右侧大框切换显示原图/校正图。
            if self.single_show_corrected:
                display_image = self.single_corrected
                right_title = "05  单面校正效果"
                right_empty = "等待校正图片"
            else:
                display_image = self.single_raw
                right_title = "05  单面原始图"
                right_empty = "等待单面图片"

            images = [
                None,
                None,
                None,
                None,
                display_image
            ]

            titles = [
                "01  正面原始图",
                "02  反面原始图",
                "03  正面校正图",
                "04  反面校正图",
                right_title
            ]

            empty_texts = [
                "单面模式",
                "单面模式",
                "单面模式",
                "单面模式",
                right_empty
            ]

        else:

            page = None

            if self.front is not None and self.back is not None:
                try:
                    page = self._build_page()
                except Exception:
                    page = None

            images = [
                self.front_raw,
                self.back_raw,
                self.front,
                self.back,
                page
            ]

            titles = [
                "01  正面原始图",
                "02  反面原始图",
                "03  正面校正图",
                "04  反面校正图",
                "05  A4 页面预览"
            ]

            empty_texts = [
                "等待正面扫描",
                "等待反面扫描",
                "等待正面校正",
                "等待反面校正",
                "等待正反面图像"
            ]

        for title_label, title in zip(
            self.preview_title_labels,
            titles
        ):
            title_label.configure(
                text=title
            )

        self._preview_images = []

        for label, image, empty_text in zip(
            self.preview_labels,
            images,
            empty_texts
        ):

            width = max(
                160,
                label.winfo_width() - 16
            )

            height = max(
                160,
                label.winfo_height() - 16
            )

            if image is None:

                label.configure(
                    image="",
                    text=empty_text
                )

                continue

            preview = fit_preview(
                image,
                (width, height)
            )

            tk_image = ImageTk.PhotoImage(
                preview
            )

            self._preview_images.append(
                tk_image
            )

            label.configure(
                image=tk_image,
                text=""
            )

    # ==================================================
    # 导入图片
    # ==================================================

    def add_image(self, side):

        if self.busy:
            return

        title_map = {
            "front": "选择正面图片",
            "back": "选择反面图片",
            "single": "选择单张图片"
        }

        path = filedialog.askopenfilename(
            parent=self.root,
            title=title_map.get(side, "选择图片"),
            filetypes=[
                (
                    "图片文件",
                    "*.jpg *.jpeg *.png *.bmp *.tif *.tiff"
                ),
                ("所有文件", "*.*")
            ]
        )

        if not path:
            return

        try:

            with Image.open(path) as source:
                raw = source.convert("RGB").copy()

            # 单面图片是整张页面，不进行证件边缘裁切。
            # 直接调用原有 A4 自动校正逻辑。
            if side == "single":

                corrected, angle = correct_a4(raw)

                self.single_raw = raw
                self.single_corrected = corrected

                # 每次导入新图片，先显示原始图
                self.single_show_corrected = False

                self.latest_raw = raw
                self.latest_corrected = corrected

                self.current_mode = "single"

                self._refresh_previews()

                self._set_status(
                    f"单张图片导入完成；倾斜校正 {angle:.2f}°"
                )

                return

            # 双面图片仍使用原来的识别和裁切逻辑
            processed, dx, dy = load_and_trim(
                path,
                self.settings["threshold"]
            )

            if side == "front":

                self.front = processed
                self.front_dpi = (dx, dy)
                self.front_raw = raw.copy()

                label = "正面"

            else:

                self.back = processed
                self.back_dpi = (dx, dy)
                self.back_raw = raw.copy()

                label = "反面"

            self.latest_raw = raw
            self.latest_corrected = processed

            self.current_mode = "duplex"

            self._refresh_previews()

            self._set_status(
                f"{label}图片导入、识别和校正完成"
            )

        except Exception as exc:

            messagebox.showerror(
                "图片导入失败",
                str(exc)
            )

    # ==================================================
    # JPG / PDF 输出
    # ==================================================

    def generate(self, fmt):

        if self.busy:
            return

        try:
            page = self._build_page()

        except Exception as exc:

            messagebox.showwarning(
                "无法导出",
                str(exc)
            )

            return

        extension = (
            ".jpg"
            if fmt == "JPG"
            else ".pdf"
        )

        filename = (
            f"ID_{datetime.now():%Y%m%d_%H%M%S}"
            f"{extension}"
        )

        initial_dir = (
            "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}"
            if os.name == "nt"
            else str(Path.home())
        )

        target = filedialog.asksaveasfilename(
            parent=self.root,
            title=f"保存{fmt}文件",
            initialdir=initial_dir,
            initialfile=filename,
            defaultextension=extension,
            filetypes=(
                [
                    ("JPG 图像", "*.jpg"),
                    ("所有文件", "*.*")
                ]
                if fmt == "JPG"
                else [
                    ("PDF 文件", "*.pdf"),
                    ("所有文件", "*.*")
                ]
            )
        )

        if not target:
            return

        try:

            save_output(
                page,
                target,
                fmt,
                dpi=300
            )

            if os.name == "nt":
                os.startfile(
                    os.path.abspath(target)
                )

            self._set_status(
                f"已生成并打开：{Path(target).name}"
            )

        except Exception as exc:

            messagebox.showerror(
                "导出失败",
                str(exc)
            )

    # ==================================================
    # 设置
    # ==================================================

    def open_settings(self):

        win = tk.Toplevel(self.root)

        win.title("IDScan 设置")
        win.geometry("680x390")
        win.resizable(False, False)
        win.transient(self.root)

        tk.Label(
            win,
            text="程序目录结构",
            font=("Microsoft YaHei UI", 15, "bold"),
            fg="#18395e"
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 12)
        )

        rows = [
            ("NAPS2 程序目录", APP_DIR),
            ("扫描命令程序", NAPS2_CONSOLE),
            ("NAPS2 主界面程序", NAPS2_GUI),
            ("扫描配置文件", PROFILE_FILE),
            ("IDScan 配置目录", CONFIG_DIR),
            ("临时输出目录", OUTPUT_DIR),
        ]

        table = tk.Frame(win)
        table.pack(
            fill="both",
            expand=True,
            padx=20
        )

        for label, path in rows:

            row = tk.Frame(table)
            row.pack(
                fill="x",
                pady=5
            )

            tk.Label(
                row,
                text=label,
                width=17,
                anchor="w",
                fg="#52667c"
            ).pack(side="left")

            exists = Path(path).exists()

            tk.Label(
                row,
                text=str(path),
                anchor="w",
                fg="#249b68" if exists else "#c17a25",
                wraplength=420
            ).pack(
                side="left",
                fill="x",
                expand=True
            )

        tk.Button(
            win,
            text="关闭",
            command=win.destroy,
            width=12,
            bg="#1769c2",
            fg="white",
            relief="flat"
        ).pack(
            anchor="e",
            padx=20,
            pady=15
        )

    # ==================================================
    # NAPS2
    # ==================================================

    def open_naps2(self):

        try:

            launch_naps2(
                NAPS2_GUI,
                working_dir=ROOT
            )

        except Exception as exc:

            messagebox.showerror(
                "无法启动 NAPS2",
                str(exc)
            )

    # ==================================================
    # 主页
    # ==================================================

    def show_home(self):

        self._set_status(
            "主页 · 准备就绪"
        )

    # ==================================================
    # 关于
    # ==================================================

    def show_about(self):

        messagebox.showinfo(
            "关于 IDScan Brother",
            "IDScan Brother 3.0\n"
            "证件扫描、自动校正与 A4 输出工具"
        )

    # ==================================================
    # 退出
    # ==================================================

    def on_close(self):

        if self.busy:

            messagebox.showwarning(
                "任务进行中",
                "扫描尚未完成，请等待扫描结束后再退出。"
            )

            return

        try:

            if OUTPUT_DIR.exists():
                shutil.rmtree(OUTPUT_DIR)

        except Exception as exc:

            messagebox.showerror(
                "清理提示",
                f"无法完全清理 Output 文件夹：\n{exc}"
            )

        self.root.destroy()


def main():

    root = tk.Tk()

    IDScanApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()