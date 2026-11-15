import os
import shutil
import threading
import ctypes
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
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

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class IDScanApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IDScan Brother 3.0")
        # 使用自定义品牌栏作为窗口标题栏
        self.root.overrideredirect(True)
        self.root.geometry("1220x790")
        self.root.minsize(1050, 700)
        self.root.configure(fg_color="#F3F6FA")
        self._window_maximized = False
        self._drag_start = None

        self.settings = load_settings()
        self.profiles = []
        self.front = self.back = None
        self.front_dpi = self.back_dpi = (300, 300)
        self.single_raw = self.single_corrected = None
        self.latest_raw = self.latest_corrected = None
        self.current_mode = "duplex"
        self.busy = False
        self._preview_images = []
        self._startup_error = ""

        self._load_profiles()
        self._build_ui()
        self._refresh_previews()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.update_idletasks()
        self._apply_borderless_resize_style()

    def _load_profiles(self):
        try:
            self.profiles = read_profiles(PROFILE_FILE)
            names = [p["display_name"] for p in self.profiles]
            current = self.settings.get("profile", "")
            if current not in names:
                self.settings["profile"] = choose_default(self.profiles)
        except Exception as exc:
            self.profiles = []
            self._startup_error = str(exc)
        save_settings(self.settings)

    def _naps2_ready(self):
        return NAPS2_CONSOLE.is_file() and bool(self.profiles)

    def _build_ui(self):
        # 3.0 蓝白专业工作台：布局按用户确认的参考界面重新组织。
        self.root.geometry("1480x1020")
        self.root.minsize(1180, 850)
        self.root.configure(fg_color="#EAF1FA")
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # 顶部自定义标题栏：品牌信息 + 窗口控制按钮
        topbar = ctk.CTkFrame(self.root, height=78, corner_radius=0, fg_color="#0759B5")
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        topbar.grid_propagate(False)
        self.topbar = topbar
        brand_title = ctk.CTkLabel(
            topbar, text="▣  IDScan Brother 3.0",
            font=ctk.CTkFont("Microsoft YaHei UI", 32, "bold"),
            text_color="#FFFFFF")
        brand_title.pack(side="left", padx=(24, 0), pady=12)
        brand_subtitle = ctk.CTkLabel(
            topbar, text="证件扫描  ·  智能校正  ·  A4 专业输出",
            font=ctk.CTkFont("Microsoft YaHei UI", 27, "bold"),
            text_color="#D9E9FF")
        brand_subtitle.pack(side="left", padx=(12, 0), pady=14)

        # 加大窗口控制按钮，并为右侧留出更明显的安全边距
        window_controls = ctk.CTkFrame(topbar, fg_color="transparent", corner_radius=0)
        window_controls.pack(side="right", padx=(0, 24), pady=8)
        ctk.CTkButton(
            window_controls, text="—", width=64, height=64, corner_radius=8,
            fg_color="transparent", hover_color="#2876C7", text_color="#FFFFFF",
            font=ctk.CTkFont(size=36, weight="bold"), command=self._minimize_window
        ).pack(side="left", padx=3)
        self.maximize_button = ctk.CTkButton(
            window_controls, text="□", width=64, height=64, corner_radius=8,
            fg_color="transparent", hover_color="#2876C7", text_color="#FFFFFF",
            font=ctk.CTkFont(size=33, weight="bold"), command=self._toggle_maximize
        )
        self.maximize_button.pack(side="left", padx=3)
        ctk.CTkButton(
            window_controls, text="×", width=64, height=64, corner_radius=8,
            fg_color="transparent", hover_color="#D83B45", text_color="#FFFFFF",
            font=ctk.CTkFont(size=40, weight="normal"), command=self.on_close
        ).pack(side="left", padx=3)

        # 品牌栏空白处可拖动窗口；双击可最大化/还原
        for drag_widget in (topbar, brand_title, brand_subtitle):
            drag_widget.bind("<ButtonPress-1>", self._start_window_drag)
            drag_widget.bind("<B1-Motion>", self._drag_window)
            drag_widget.bind("<Double-Button-1>", lambda _event: self._toggle_maximize())

        # 左侧导航
        nav = ctk.CTkFrame(self.root, width=92, corner_radius=0, fg_color="#F7FAFF",
                           border_width=1, border_color="#D8E3F1")
        nav.grid(row=1, column=0, sticky="nsew")
        nav.grid_propagate(False)
        ctk.CTkLabel(nav, text="IDSCAN", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#7890AD").pack(pady=(24, 18))
        self._nav_button(nav, "⌂", "主页", self.show_home, True)
        self._nav_button(nav, "⚙", "设置", self.open_settings)
        self._nav_button(nav, "▣", "NAPS2", self.open_naps2)
        self._nav_button(nav, "ⓘ", "关于", self.show_about)
        ctk.CTkLabel(nav, text="VERSION\n3.0", justify="center",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#9AABC0").pack(side="bottom", pady=20)

        content = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        content.grid(row=1, column=1, sticky="nsew", padx=22, pady=18)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        # 工作台标题和设备状态
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="证件扫描工作台",
                     font=ctk.CTkFont("Microsoft YaHei UI", 36, "bold"),
                     text_color="#102B50").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="选择扫描配置：", text_color="#526A87",
                     font=ctk.CTkFont(size=18)).grid(row=0, column=1, padx=(8, 6))
        names = [p["display_name"] for p in self.profiles] or ["未发现扫描配置"]
        self.profile_var = tk.StringVar(value=self.settings.get("profile") or names[0])
        self.profile_menu = ctk.CTkOptionMenu(
            header, variable=self.profile_var, values=names, width=280, height=48,
            font=ctk.CTkFont(size=18),
            dropdown_font=ctk.CTkFont(size=17),
            fg_color="#FFFFFF", button_color="#1769C2", button_hover_color="#0E55A4",
            text_color="#18395E", dropdown_fg_color="#FFFFFF", command=self._profile_changed)
        self.profile_menu.grid(row=0, column=2, padx=(0, 12))
        ready = self._naps2_ready()
        self.status_dot = ctk.CTkLabel(
            header, text="● 扫描仪已就绪" if ready else "● 扫描配置未就绪",
            text_color="#15945D" if ready else "#C17A25",
            font=ctk.CTkFont(size=17, weight="bold"))
        self.status_dot.grid(row=0, column=3, padx=(4, 8))
        if not self.profiles:
            self.profile_menu.configure(state="disabled")

        # 三个并列预览窗
        self.preview_area = ctk.CTkFrame(content, fg_color="#FFFFFF", corner_radius=14,
                                         border_width=1, border_color="#D5E1EF")
        self.preview_area.grid(row=1, column=0, sticky="nsew", pady=(0, 14))
        self.preview_area.grid_columnconfigure((0, 1, 2), weight=1, uniform="preview")
        self.preview_area.grid_rowconfigure(1, weight=1)
        self.preview_labels = []
        self.action_buttons = []
        header_colors = ["#1769C2", "#159B69", "#6257C9"]
        titles = ["01  原始扫描图", "02  识别校正后", "03  A4 页面预览"]
        for i, (title, color) in enumerate(zip(titles, header_colors)):
            card = ctk.CTkFrame(self.preview_area, fg_color="#F7FAFE", corner_radius=10,
                                border_width=1, border_color="#E0E8F2")
            card.grid(row=0, column=i, sticky="nsew", padx=(12 if i == 0 else 7, 7 if i < 2 else 12), pady=12)
            card.grid_rowconfigure(1, weight=1)
            card.grid_columnconfigure(0, weight=1)
            titlebar = ctk.CTkFrame(card, height=52, corner_radius=8, fg_color=color)
            titlebar.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
            titlebar.grid_propagate(False)
            ctk.CTkLabel(titlebar, text=title, text_color="#FFFFFF",
                         font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=14, pady=8)
            preview = ctk.CTkLabel(card, text="等待扫描图像", fg_color="#EAF0F7",
                                   corner_radius=7, text_color="#8A9CB1",
                                   font=ctk.CTkFont(size=18))
            preview.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
            self.preview_labels.append(preview)
            if i in (0, 1):
                side = "front" if i == 0 else "back"
                button = ctk.CTkButton(card, text="＋ 导入正面图片" if i == 0 else "＋ 导入反面图片",
                                       height=42, corner_radius=7, fg_color="#E6F0FC",
                                       hover_color="#D5E6FA", text_color="#1762AE",
                                       font=ctk.CTkFont(size=18, weight="bold"),
                                       command=lambda s=side: self.add_image(s))
                button.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
                self.action_buttons.append(button)
        self.preview_area.bind("<Configure>", lambda _e: self.root.after_idle(self._refresh_previews))

        # 底部操作区：左侧扫描/排版，右侧导出
        bottom = ctk.CTkFrame(content, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=3)
        bottom.grid_columnconfigure(1, weight=1)

        controls = ctk.CTkFrame(bottom, fg_color="#FFFFFF", corner_radius=13,
                                border_width=1, border_color="#D5E1EF")
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(controls, text="扫描与图像处理", text_color="#17375D",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 5))

        row1 = ctk.CTkFrame(controls, fg_color="transparent")
        row1.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        for label, command, color in [
            ("▣  扫描正面", lambda: self.start_scan("front"), "#1769C2"),
            ("▣  扫描反面", lambda: self.start_scan("back"), "#1769C2"),
            ("▤  扫描单面", lambda: self.start_scan("single"), "#1769C2"),
        ]:
            button = ctk.CTkButton(row1, text=label, command=command, height=54,
                                   corner_radius=8, fg_color=color, hover_color="#0E55A4",
                                   font=ctk.CTkFont(size=19, weight="bold"))
            button.pack(side="left", expand=True, fill="x", padx=4)
            self.action_buttons.append(button)

        row2 = ctk.CTkFrame(controls, fg_color="transparent")
        row2.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        self.arrangement = tk.StringVar(value=self.settings.get("arrangement", "左右排列"))
        for label, value in [("⇄  左右排列", "左右排列"), ("⇵  上下排列", "上下排列"), ("⌁  单面校正", "单面校正")]:
            button = ctk.CTkButton(row2, text=label, height=50, corner_radius=8,
                                   fg_color="#E8F1FC", text_color="#1B5E9E",
                                   hover_color="#D7E7F8",
                                   font=ctk.CTkFont(size=18, weight="bold"),
                                   command=lambda v=value: self.change_layout(v))
            button.pack(side="left", expand=True, fill="x", padx=4)
            self.action_buttons.append(button)
        ctk.CTkLabel(controls, text="扫描正反面后可实时预览 A4 排版；单面模式用于整页扫描与倾斜校正。",
                     text_color="#8294A9", font=ctk.CTkFont(size=15)).grid(row=3, column=0, sticky="w", padx=17, pady=(5, 11))

        export = ctk.CTkFrame(bottom, fg_color="#FFFFFF", corner_radius=13,
                              border_width=1, border_color="#D5E1EF")
        export.grid(row=0, column=1, sticky="nsew")
        export.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(export, text="文件输出", text_color="#17375D",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))
        self.export_jpg = ctk.CTkButton(export, text="▧  生成 JPG 图像", height=58,
                                        corner_radius=8, fg_color="#20A85A", hover_color="#168849",
                                        font=ctk.CTkFont(size=19, weight="bold"),
                                        command=lambda: self.generate("JPG"))
        self.export_jpg.grid(row=1, column=0, sticky="ew", padx=13, pady=5)
        self.export_pdf = ctk.CTkButton(export, text="▤  生成 PDF 文件", height=58,
                                        corner_radius=8, fg_color="#6559C9", hover_color="#5045B0",
                                        font=ctk.CTkFont(size=19, weight="bold"),
                                        command=lambda: self.generate("PDF"))
        self.export_pdf.grid(row=2, column=0, sticky="ew", padx=13, pady=5)
        self.action_buttons.extend([self.export_jpg, self.export_pdf])
        ctk.CTkLabel(export, text="A4 竖向 · 300 DPI", text_color="#8192A8",
                     font=ctk.CTkFont(size=15)).grid(row=3, column=0, pady=(4, 10))

        # 底部状态栏
        self.status_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.status_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.status_text = ctk.CTkLabel(
            self.status_frame, text="准备就绪",
            text_color="#526A87", anchor="w",
            font=ctk.CTkFont(size=17)
        )
        self.status_text.pack(fill="x")
        self.progress = ctk.CTkProgressBar(self.status_frame, mode="indeterminate", height=6)
        self.progress.set(0)

    def _nav_button(self, parent, icon, text, command, active=False):
        """左侧导航：图标与文字同步放大，导航栏略微收窄。"""
        normal_bg = "#F7FAFF"
        active_bg = "#E2EEFC" if active else normal_bg
        item = ctk.CTkFrame(parent, height=108, corner_radius=10,
                            fg_color=active_bg, border_width=0)
        item.pack(fill="x", padx=6, pady=6)
        item.pack_propagate(False)

        icon_label = ctk.CTkLabel(
            item, text=icon, text_color="#1769C2" if active else "#294665",
            font=ctk.CTkFont(size=42, weight="bold"), height=54)
        icon_label.pack(pady=(6, 0))
        text_label = ctk.CTkLabel(
            item, text=text, text_color="#1769C2" if active else "#294665",
            font=ctk.CTkFont(size=22, weight="bold"), height=34)
        text_label.pack(pady=(0, 4))

        for widget in (item, icon_label, text_label):
            widget.bind("<Button-1>", lambda _event, cb=command: cb())
            widget.bind("<Enter>", lambda _event, frame=item: frame.configure(fg_color="#E2EEFC"))
            widget.bind("<Leave>", lambda _event, frame=item, bg=active_bg: frame.configure(fg_color=bg))

    def _apply_borderless_resize_style(self):
        """Windows 下保留无标题栏窗口的系统边缘缩放能力。"""
        if os.name != "nt":
            return
        try:
            hwnd = self.root.winfo_id()
            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000
            WS_SYSMENU = 0x00080000
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020

            get_style = ctypes.windll.user32.GetWindowLongW
            set_style = ctypes.windll.user32.SetWindowLongW
            style = get_style(hwnd, GWL_STYLE)
            style |= WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
            set_style(hwnd, GWL_STYLE, style)
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            # 自定义标题栏仍可使用；仅系统边缘缩放增强不可用时忽略。
            pass

    def _start_window_drag(self, event):
        if self._window_maximized:
            return
        self._drag_start = (event.x_root, event.y_root,
                            self.root.winfo_x(), self.root.winfo_y())

    def _drag_window(self, event):
        if not self._drag_start or self._window_maximized:
            return
        start_x, start_y, win_x, win_y = self._drag_start
        new_x = win_x + event.x_root - start_x
        new_y = win_y + event.y_root - start_y
        self.root.geometry(f"+{new_x}+{new_y}")

    def _minimize_window(self):
        try:
            if os.name == "nt":
                ctypes.windll.user32.ShowWindow(self.root.winfo_id(), 6)  # SW_MINIMIZE
            else:
                self.root.overrideredirect(False)
                self.root.iconify()
                self.root.after(300, lambda: self.root.overrideredirect(True))
        except Exception:
            self.root.iconify()

    def _toggle_maximize(self):
        try:
            if os.name == "nt":
                hwnd = self.root.winfo_id()
                if self._window_maximized:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    self._window_maximized = False
                    self.maximize_button.configure(text="□")
                else:
                    ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                    self._window_maximized = True
                    self.maximize_button.configure(text="❐")
            else:
                if self._window_maximized:
                    self.root.state("normal")
                    self._window_maximized = False
                    self.maximize_button.configure(text="□")
                else:
                    self.root.overrideredirect(False)
                    self.root.state("zoomed")
                    self.root.after(250, lambda: self.root.overrideredirect(True))
                    self._window_maximized = True
                    self.maximize_button.configure(text="❐")
        except Exception as exc:
            messagebox.showerror("窗口操作失败", str(exc))

    def _profile_changed(self, value):
        self.settings["profile"] = value
        save_settings(self.settings)

    def _set_status(self, text, busy=False):
        self.status_text.configure(text=text)
        if busy:
            self.progress.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.grid_forget()
        self.busy = busy
        for button in self.action_buttons:
            button.configure(state="disabled" if busy else "normal")
        self.profile_menu.configure(state="disabled" if busy or not self.profiles else "normal")

    def start_scan(self, side):
        if not NAPS2_CONSOLE.is_file():
            messagebox.showwarning("NAPS2 程序缺失", f"找不到：\n{NAPS2_CONSOLE}\n\n请将 NAPS2 程序文件放入项目根目录下的 app 文件夹。")
            return
        profile = self.profile_var.get().strip()
        if not self.profiles or profile == "未发现扫描配置":
            messagebox.showwarning("没有扫描配置", f"请检查：\n{PROFILE_FILE}")
            return

        side_name = {"front": "正面", "back": "反面", "single": "单面"}[side]
        output = OUTPUT_DIR / f"scan_{side}_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
        self._set_status(f"正在扫描{side_name}，请稍候……", True)

        def worker():
            try:
                scan_to_image(NAPS2_CONSOLE, profile, output, working_dir=ROOT)
                with Image.open(output) as source:
                    raw = source.convert("RGB").copy()
                if side in ("front", "back"):
                    processed, dx, dy = load_and_trim(output, self.settings["threshold"])
                    self.root.after(0, lambda: self._scan_done(side, raw, processed, dx, dy))
                else:
                    corrected, angle = correct_a4(raw)
                    self.root.after(0, lambda: self._single_done(raw, corrected, angle))
            except Exception as exc:
                error = str(exc)
                self.root.after(0, lambda e=error: self._scan_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _scan_done(self, side, raw, processed, dx, dy):
        if side == "front":
            self.front, self.front_dpi = processed, (dx, dy)
            label = "正面"
        else:
            self.back, self.back_dpi = processed, (dx, dy)
            label = "反面"
        self.latest_raw, self.latest_corrected = raw, processed
        self.current_mode = "duplex"
        self._set_status(f"{label}扫描、识别和校正完成")
        self._refresh_previews()

    def _single_done(self, raw, corrected, angle):
        self.single_raw, self.single_corrected = raw, corrected
        self.latest_raw, self.latest_corrected = raw, corrected
        self.current_mode = "single"
        self._set_status(f"单面扫描完成；倾斜校正 {angle:.2f}°")
        self._refresh_previews()

    def _scan_error(self, error):
        self._set_status("扫描失败")
        messagebox.showerror("扫描错误", error)

    def change_layout(self, value):
        if value == "单面校正":
            if self.single_corrected is None:
                messagebox.showinfo("单面校正", "请先点击“扫单面”，扫描一张整页文件。")
                return
            self.current_mode = "single"
        else:
            self.arrangement.set(value)
            self.settings["arrangement"] = value
            self.current_mode = "duplex"
        save_settings(self.settings)
        self._refresh_previews()
        self._set_status("单面校正预览" if self.current_mode == "single" else f"页面排列：{value}")

    def _build_page(self):
        if self.current_mode == "single":
            if self.single_corrected is None:
                raise ValueError("请先扫描单面文件。")
            return self.single_corrected
        if self.front is None or self.back is None:
            raise ValueError("请先扫描正面和反面。")
        return compose_a4(
            self.front, self.back, self.front_dpi, self.back_dpi,
            self.arrangement.get(), output_dpi=300,
            margin_mm=self.settings["margin_mm"], gap_mm=self.settings["gap_mm"],
        )

    def _refresh_previews(self):
        if not hasattr(self, "preview_labels"):
            return
        if self.current_mode == "single":
            images = [self.single_raw, self.single_corrected, self.single_corrected]
        else:
            page = None
            if self.front is not None and self.back is not None:
                try:
                    page = self._build_page()
                except Exception:
                    page = None
            images = [self.latest_raw, self.latest_corrected, page]

        self._preview_images = []
        for label, image in zip(self.preview_labels, images):
            width = max(160, label.winfo_width() - 16)
            height = max(180, label.winfo_height() - 16)
            if image is None:
                label.configure(image=None, text="等待扫描", compound="center")
                continue
            preview = fit_preview(image, (width, height))
            tk_image = ImageTk.PhotoImage(preview)
            self._preview_images.append(tk_image)
            label.configure(image=tk_image, text="", compound="center")

    def add_image(self, side):
        path = filedialog.askopenfilename(
            parent=self.root, title="选择正面图片" if side == "front" else "选择反面图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            raw = Image.open(path).convert("RGB")
            processed, dx, dy = load_and_trim(path, self.settings["threshold"])
            if side == "front":
                self.front, self.front_dpi = processed, (dx, dy)
            else:
                self.back, self.back_dpi = processed, (dx, dy)
            self.latest_raw, self.latest_corrected = raw, processed
            self.current_mode = "duplex"
            self._refresh_previews()
            self._set_status(("正面" if side == "front" else "反面") + "图片导入、识别和校正完成")
        except Exception as exc:
            messagebox.showerror("图片导入失败", str(exc))

    def generate(self, fmt):
        try:
            page = self._build_page()
        except Exception as exc:
            messagebox.showwarning("无法导出", str(exc))
            return

        extension = ".jpg" if fmt == "JPG" else ".pdf"
        filename = f"ID_{datetime.now():%Y%m%d_%H%M%S}{extension}"
        initial_dir = "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}" if os.name == "nt" else str(Path.home())
        target = filedialog.asksaveasfilename(
            parent=self.root, title=f"保存{fmt}文件", initialdir=initial_dir,
            initialfile=filename, defaultextension=extension,
            filetypes=[("JPG 图像", "*.jpg"), ("所有文件", "*.*")] if fmt == "JPG" else [("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
        )
        if not target:
            return
        try:
            save_output(page, target, fmt, dpi=300)
            if os.name == "nt":
                os.startfile(os.path.abspath(target))
            self._set_status(f"已生成并打开：{Path(target).name}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def open_settings(self):
        win = ctk.CTkToplevel(self.root)
        win.title("IDScan 设置")
        win.geometry("720x460")
        win.transient(self.root)
        win.grab_set()
        win.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(win, text="程序目录结构", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 12), sticky="w")
        rows = [
            ("NAPS2 程序目录", APP_DIR),
            ("扫描命令程序", NAPS2_CONSOLE),
            ("NAPS2 主界面程序", NAPS2_GUI),
            ("扫描配置文件", PROFILE_FILE),
            ("IDScan 配置目录", CONFIG_DIR),
            ("临时输出目录", OUTPUT_DIR),
        ]
        for index, (label, path) in enumerate(rows, start=1):
            ctk.CTkLabel(win, text=label, text_color="#52667C", font=ctk.CTkFont(size=15)).grid(row=index, column=0, padx=20, pady=7, sticky="w")
            exists = Path(path).exists()
            ctk.CTkLabel(win, text=str(path), text_color="#249B68" if exists else "#C17A25", anchor="w", wraplength=450, font=ctk.CTkFont(size=14)).grid(row=index, column=1, padx=12, pady=7, sticky="ew")
        ctk.CTkLabel(win, text="NAPS2 不进行全盘搜索；请按项目目录结构放置程序和 profiles.xml。", text_color="#75879A", wraplength=620, font=ctk.CTkFont(size=14)).grid(row=7, column=0, columnspan=2, padx=20, pady=(12, 4), sticky="w")
        ctk.CTkButton(win, text="关闭", command=win.destroy, width=120, height=42, font=ctk.CTkFont(size=16)).grid(row=8, column=1, padx=20, pady=14, sticky="e")

    def open_naps2(self):
        try:
            launch_naps2(NAPS2_GUI, working_dir=ROOT)
        except Exception as exc:
            messagebox.showerror("无法启动 NAPS2", str(exc))

    def show_home(self):
        self._set_status("主页 · 准备就绪")

    def show_about(self):
        messagebox.showinfo("关于 IDScan Brother", "IDScan Brother 3.0\n证件扫描、自动校正与 A4 输出工具")

    def on_close(self):
        if self.busy:
            messagebox.showwarning("任务进行中", "扫描尚未完成，请等待扫描结束后再退出。")
            return
        try:
            if OUTPUT_DIR.exists():
                shutil.rmtree(OUTPUT_DIR)
        except Exception as exc:
            messagebox.showerror("清理提示", f"无法完全清理 Output 文件夹：\n{exc}")
        self.root.destroy()


def main():
    # UI 62.5% 缩放测试
    ctk.set_widget_scaling(0.625)
    ctk.set_window_scaling(0.625)
    root = ctk.CTk()
    IDScanApp(root)
    root.mainloop()
