"""PySide6 user interface."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import traceback
from typing import Callable, Optional

from PySide6.QtCore import QObject, QRectF, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from . import lan, mods, patches, paths, profile, updates
from .core import Core, GT6_TITLES
from .rpcs3 import RPCS3, STOCK_BUILD_WARNING, installed_version, is_patched_build

ACCENT = "#e0157a"
STYLE = f"""
* {{ color: #e9e9ee; font-size: 10pt; }}
QMainWindow, QDialog, QMessageBox {{ background: #0b0b10; }}
QTabWidget::pane {{ border: 1px solid rgba(255,255,255,0.08); background: rgba(10,10,14,0.86); border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: transparent; padding: 9px 15px; color: #9a9aa6; border: none; font-weight: 600; }}
QTabBar::tab:selected {{ color: white; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: white; }}
QGroupBox {{ border: 1px solid rgba(255,255,255,0.09); border-radius: 8px; margin-top: 14px; padding: 12px 10px 10px 10px; background: rgba(255,255,255,0.025); }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #c9c9d4; font-weight: 700; }}
QPushButton {{ background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; padding: 6px 12px; }}
QPushButton:hover {{ background: rgba(255,255,255,0.13); }}
QPushButton:disabled {{ color: #66666f; background: rgba(255,255,255,0.03); }}
QPushButton#accent {{ background: {ACCENT}; border: none; color: white; font-weight: 700; }}
QPushButton#accent:hover {{ background: #ff3d97; }}
QPushButton#play {{ background: {ACCENT}; border: none; color: white; font-size: 20pt; font-weight: 800; letter-spacing: 3px; border-radius: 10px; padding: 14px; }}
QPushButton#play:hover {{ background: #ff3d97; }}
QPushButton#play:disabled {{ background: #3a2230; color: #9a7a8a; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QListWidget {{ background: rgba(0,0,0,0.45); border: 1px solid rgba(255,255,255,0.12); border-radius: 5px; padding: 4px 6px; selection-background-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: #15151b; selection-background-color: {ACCENT}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid #77778a; background: rgba(0,0,0,0.4); }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QProgressBar {{ background: rgba(0,0,0,0.5); border: none; border-radius: 4px; height: 10px; text-align: center; font-size: 8pt; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QLabel#muted {{ color: #9a9aa6; }}
QLabel#warn {{ color: #ffb347; }}
QLabel#ok {{ color: #6fdc8c; }}
QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.15); border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; margin: -6px 0; border-radius: 7px; background: {ACCENT}; }}
QToolTip {{ background: #15151b; color: white; border: 1px solid #333; }}
"""


# --------------------------------------------------------------------------- helpers

class Background(QWidget):
    """Key art cover-scaled on the left, strongly darkened, fading to near-black
    under the controls."""

    def __init__(self, image: str):
        super().__init__()
        self.img = QImage(image)

    visible_right = 0  # x where the tab panel starts (set by MainWindow)

    def paintEvent(self, _):
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, QColor("#07070a"))
        if self.img.isNull():
            return
        edge = max(self.visible_right or int(r.width() * 0.42), 320)
        # cover the full height and at least the visible left area
        scale = max(edge / (self.img.width() * 0.97), r.height() / self.img.height())
        w, h = self.img.width() * scale, self.img.height() * scale
        # right-align: the logo sits in the right part of the art, keep it in view;
        # crop from the left instead.
        x = min(0.0, edge - w * 0.97)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QRectF(x, 0, w, h), self.img)
        p.fillRect(r, QColor(0, 0, 0, 115))  # global darken
        g = QLinearGradient(edge - 50, 0, edge + 30, 0)
        g.setColorAt(0.0, QColor(7, 7, 10, 0))
        g.setColorAt(1.0, QColor(7, 7, 10, 255))
        p.fillRect(QRectF(edge - 50, 0, 80, r.height()), g)
        p.fillRect(QRectF(edge + 30, 0, r.width(), r.height()), QColor(7, 7, 10))
        v = QLinearGradient(0, r.height() * 0.40, 0, r.height())
        v.setColorAt(0, QColor(7, 7, 10, 0))
        v.setColorAt(1, QColor(7, 7, 10, 240))
        p.fillRect(r, v)


def label(text: str = "", size: int = 10, bold: bool = False, name: str = "", wrap: bool = True) -> QLabel:
    lb = QLabel(text)
    f = lb.font()
    f.setPointSize(size)
    f.setBold(bold)
    lb.setFont(f)
    lb.setWordWrap(wrap)
    lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if name:
        lb.setObjectName(name)
    return lb


def wrap_path(text: str) -> str:
    """Allow long paths to wrap at separators (zero-width space after / and \\)."""
    return text.replace("/", "/\u200b").replace("\\", "\\\u200b")


def scroll(inner: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    s.setWidgetResizable(True)
    s.setWidget(inner)
    return s


def restyle(w: QWidget, name: str) -> None:
    w.setObjectName(name)
    w.style().unpolish(w)
    w.style().polish(w)


class _Relay(QObject):
    """Runs ``fn`` on the GUI thread when connected to a worker signal.

    PySide6 runs a plain Python callable connected to a signal on the *emitting* thread.
    Worker-thread code that touches widgets (message boxes, refresh) then hangs on Windows
    ("Not responding" blank dialog). A slot of a QObject that lives in the GUI thread is
    queued to that thread instead."""

    def __init__(self, fn: Callable, parent: QObject):
        super().__init__(parent)
        self.fn = fn

    @Slot()
    @Slot(object)
    def call(self, *a) -> None:
        self.fn(*a)


def _on_gui(signal, fn: Callable, owner: QObject) -> "_Relay":
    r = _Relay(fn, owner)
    signal.connect(r.call)
    return r


class Job(QObject):
    """Runs fn(job) on a worker thread. fn can call job.progress(label, done, total) and job.log()."""
    progressed = Signal(str, object, object)
    logged = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable):
        super().__init__()
        self.fn = fn
        self.cancel_event = threading.Event()
        self.downloader: Optional[updates.Downloader] = None

    def progress(self, text: str, done: int, total: int) -> None:
        self.progressed.emit(text, done, total)

    def log(self, s: str) -> None:
        self.logged.emit(s)

    def cancel(self) -> None:
        self.cancel_event.set()
        if self.downloader:
            self.downloader.cancel()

    def run(self) -> None:
        try:
            self.done.emit(self.fn(self))
        except updates.Cancelled:
            self.failed.emit("Cancelled")
        except Exception as e:  # noqa: BLE001
            self.logged.emit(traceback.format_exc())
            self.failed.emit(f"{e}")


# --------------------------------------------------------------------------- main window

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from . import __version__
        self.setWindowTitle(f"Gran Turismo 6 PC  v{__version__}")
        self.setWindowIcon(QIcon(paths.resource("img/icon.png")))
        self.resize(1240, 780)
        self.core = Core(log=self._log_threadsafe)
        self.s = self.core.settings
        self.thread: Optional[QThread] = None
        self.job: Optional[Job] = None
        self.proc: Optional[subprocess.Popen] = None
        self._loading = False
        self._patch_index: Optional[list] = None

        bg = Background(paths.resource("img/bg.png"))
        self.setCentralWidget(bg)
        self._bgw = bg
        root = QHBoxLayout(bg)
        root.setContentsMargins(28, 24, 24, 20)
        root.setSpacing(24)
        root.addWidget(self._build_left(), 4)
        self.ctl: dict[str, QWidget] = {}
        self.tabs = QTabWidget()
        self.tabs.addTab(scroll(self._build_setup()), "Setup")
        self.tabs.addTab(scroll(self._build_graphics()), "Graphics")
        self.tabs.addTab(self._build_patches(), "Patches")
        self.tabs.addTab(scroll(self._build_mods()), "Mods")
        self.tabs.addTab(scroll(self._build_lan()), "LAN")
        self.tabs.addTab(scroll(self._build_advanced()), "Advanced")
        self.tabs.addTab(self._build_log(), "Log")
        root.addWidget(self.tabs, 6)

        self._logsig_holder = _LogBridge()
        self._logsig_holder.line.connect(self._append_log)
        for cb in self.findChildren(QComboBox):  # let long entries shrink instead of widening the page
            cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(14)
        for kind in (QComboBox, QSpinBox, QDoubleSpinBox, QSlider):
            for wdg in self.findChildren(kind):
                wdg.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # never grab focus from the mouse wheel
        self._load_settings_into_ui()
        self._fill_pads()
        self._update_wheel_label()
        self.refresh()
        self.poll = QTimer(self)
        self.poll.timeout.connect(self._poll_proc)
        self.poll.start(1000)
        QTimer.singleShot(200, self._first_run)

    # ------------------------------------------------------------------ left panel
    def _build_left(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(label("GRAN TURISMO 6", 26, True))
        from . import __version__
        v.addWidget(label(f"PC edition  ·  v{__version__}", 11, False, "muted"))
        v.addStretch(1)
        self.game_box = QComboBox()
        self.game_box.currentIndexChanged.connect(self._on_game_changed)
        v.addWidget(self.game_box)
        self.status_lbl = label("", 10)
        v.addWidget(self.status_lbl)
        self.build_lbl = label("", 9, False, "warn")
        v.addWidget(self.build_lbl)
        self.progress_lbl = label("", 9, False, "muted")
        v.addWidget(self.progress_lbl)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        v.addWidget(self.progress)
        row = QHBoxLayout()
        self.play_btn = QPushButton("PLAY")
        self.play_btn.setObjectName("play")
        self.play_btn.clicked.connect(self.play)
        row.addWidget(self.play_btn, 1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_job)
        self.cancel_btn.hide()
        row.addWidget(self.cancel_btn)
        v.addLayout(row)
        self.lan_quick = QCheckBox("LAN mode (secret lanmode)")
        self.lan_quick.toggled.connect(lambda b: self._set("lan_enabled", b))
        v.addWidget(self.lan_quick)
        return w

    # ------------------------------------------------------------------ setup tab
    def _build_setup(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("1. PS3 firmware")
        f = QVBoxLayout(g)
        self.fw_lbl = label()
        f.addWidget(self.fw_lbl)
        h = QHBoxLayout()
        self.fw_btn = QPushButton("Install firmware")
        self.fw_btn.setObjectName("accent")
        self.fw_btn.clicked.connect(self.install_firmware)
        h.addWidget(self.fw_btn)
        b = QPushButton("Choose PS3UPDAT.PUP...")
        b.clicked.connect(self.pick_firmware)
        h.addWidget(b)
        h.addStretch(1)
        f.addLayout(h)
        f.addWidget(label("If no PUP file is found locally it is downloaded from Sony's update server.", 9, name="muted"))
        v.addWidget(g)

        g = QGroupBox("2. Game disc")
        f = QVBoxLayout(g)
        self.games_lbl = label()
        f.addWidget(self.games_lbl)
        h = QHBoxLayout()
        b = QPushButton("Add ISO...")
        b.clicked.connect(self.pick_iso)
        h.addWidget(b)
        b = QPushButton("Add folder...")
        b.clicked.connect(self.pick_folder)
        h.addWidget(b)
        b = QPushButton("Scan for ISOs")
        b.clicked.connect(self.scan_isos)
        h.addWidget(b)
        h.addStretch(1)
        f.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Console language"))
        self.ctl["console_language"] = self._combo({k: ("Automatic (from the disc region)" if k == "auto" else k)
                                                    for k in profile.LANGUAGES}, "console_language")
        h.addWidget(self.ctl["console_language"], 1)
        f.addLayout(h)
        f.addWidget(label("The emulated PS3's region always matches the disc (EU disc = European console), so the "
                          "game starts with the right defaults. The language also sets the game text on the "
                          "multi-language EU disc. In-game settings worth changing once (stored in your "
                          "save): Options -> Display -> Display Size (HD) = 100 removes the black border; "
                          "Options -> Global -> Units for km/h / mph.", 9, name="muted"))
        v.addWidget(g)

        g = QGroupBox("3. Controllers")
        f = QVBoxLayout(g)
        h = QHBoxLayout()
        h.addWidget(QLabel("Player 1"))
        self.pad_box = QComboBox()
        self.pad_box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pad_box.currentIndexChanged.connect(self._on_pad_changed)
        h.addWidget(self.pad_box, 1)
        b = QPushButton("Refresh")
        b.clicked.connect(lambda: (self._fill_pads(), self._update_wheel_label()))
        h.addWidget(b)
        f.addLayout(h)
        self.pad_lbl = label("", 9, name="muted")
        f.addWidget(self.pad_lbl)
        f.addWidget(label("Automatic uses the first detected gamepad (Xbox, PlayStation, 8BitDo, Switch Pro ...) "
                          "with standard button mapping; if none is detected, the current RPCS3 input setting is kept. "
                          "Choose Keyboard explicitly to switch to keyboard input. Racing-game style "
                          "triggers (RT accelerate, LT brake): in the game, Options -> Wireless Controller.", 9, name="muted"))
        h = QHBoxLayout()
        self.wheel_chk = QCheckBox("Use racing wheel")
        self.wheel_chk.toggled.connect(self._on_wheel_toggled)
        h.addWidget(self.wheel_chk)
        b = QPushButton("Set up wheel...")
        b.clicked.connect(self.setup_wheel)
        h.addWidget(b)
        self.wheel_lbl = label("", 9, name="muted")
        h.addWidget(self.wheel_lbl, 1)
        f.addLayout(h)
        f.addWidget(label("Any wheel (Logitech, Thrustmaster, Fanatec, Moza ...) works: the game sees it as a Logitech "
                          "G27, which GT6 supports natively, including force feedback. The set-up asks you to turn "
                          "the wheel and press each pedal/button once.", 9, name="muted"))
        v.addWidget(g)

        g = QGroupBox("4. Game updates")
        f = QVBoxLayout(g)
        self.upd_lbl = label()
        f.addWidget(self.upd_lbl)
        form = QFormLayout()
        self.target_box = QComboBox()
        self.target_box.currentIndexChanged.connect(self._on_target_changed)
        form.addRow("Target version", self.target_box)
        self.target_hint = label("", 9, name="muted")
        form.addRow("", self.target_hint)
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 8)
        self.parallel_spin.valueChanged.connect(lambda n: self._set_data("parallel", n))
        form.addRow("Parallel downloads", self.parallel_spin)
        self.delete_pkgs = QCheckBox("Delete update packages after installing (saves ~10 GB)")
        self.delete_pkgs.toggled.connect(lambda b: self._set_data("delete_pkgs", b))
        form.addRow("", self.delete_pkgs)
        f.addLayout(form)
        h = QHBoxLayout()
        self.upd_btn = QPushButton("Download && install updates")
        self.upd_btn.setObjectName("accent")
        self.upd_btn.clicked.connect(self.install_updates)
        h.addWidget(self.upd_btn)
        h.addStretch(1)
        f.addLayout(h)
        f.addWidget(label("Updates are installed in order (1.02 -> 1.22, 1.01 is skipped), downloads resume and "
                          "every package is SHA-1 checked. After installing, start the game once so it can unpack "
                          "its update data - only then install mods.", 9, name="muted"))
        v.addWidget(g)
        v.addStretch(1)
        return w

    def _fill_pads(self) -> None:
        from . import gamepad
        pads = gamepad.list_gamepads()
        self._loading = True
        self.pad_box.clear()
        self.pad_box.addItem("Automatic (first gamepad, else keyboard)", ("auto", ""))
        for p in pads or []:
            self.pad_box.addItem(p, ("pad", p))
        if self.s.controller_mode == "pad" and self.s.controller_device not in (pads or []):
            self.pad_box.addItem(f"{self.s.controller_device} (not connected)", ("pad", self.s.controller_device))
        self.pad_box.addItem("Keyboard", ("keyboard", ""))
        want = (self.s.controller_mode, self.s.controller_device if self.s.controller_mode == "pad" else "")
        for i in range(self.pad_box.count()):
            if tuple(self.pad_box.itemData(i)) == want:
                self.pad_box.setCurrentIndex(i)
        self._loading = False
        if pads is None:
            self.pad_lbl.setText("Gamepad detection unavailable (SDL3 library not found).")
        elif not pads:
            self.pad_lbl.setText("No gamepad connected. Connect it (8BitDo: X-input mode) and click Refresh."
                                 if paths.IS_WINDOWS else "No gamepad connected.")
        else:
            self.pad_lbl.setText(f"Connected: {', '.join(pads)}" if pads else "No gamepad connected.")

    def _on_pad_changed(self, _i) -> None:
        if self._loading:
            return
        mode, dev = self.pad_box.currentData()
        self.s.controller_mode, self.s.controller_device = mode, dev
        self.core.save()

    def _update_wheel_label(self) -> None:
        m = self.s.wheel_mapping or {}
        if m.get("steering"):
            n = len([k for k in m if m[k]])
            self.wheel_lbl.setText(f"Set up: {self.s.wheel_name or 'wheel'} ({n} controls mapped)")
        else:
            self.wheel_lbl.setText("Not set up yet.")
        self._loading = True
        self.wheel_chk.setChecked(bool(self.s.wheel_enabled and m.get("steering")))
        self._loading = False

    def _on_wheel_toggled(self, on: bool) -> None:
        if self._loading:
            return
        if on and not (self.s.wheel_mapping or {}).get("steering"):
            self._loading = True
            self.wheel_chk.setChecked(False)
            self._loading = False
            self.setup_wheel()
            return
        self.s.wheel_enabled = on
        self.core.save()

    def setup_wheel(self) -> None:
        try:
            dlg = WheelWizard(self)
        except RuntimeError as e:
            QMessageBox.warning(self, "Racing wheel", f"Wheel detection is unavailable: {e}")
            return
        if dlg.exec() and dlg.mapping.get("steering"):
            self.s.wheel_mapping = dlg.mapping
            self.s.wheel_name = dlg.wheel_name
            self.s.wheel_enabled = True
            self.core.save()
        self._update_wheel_label()

    # ------------------------------------------------------------------ graphics tab
    def _combo(self, items: dict | list, key: str, cast=str) -> QComboBox:
        c = QComboBox()
        c.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if isinstance(items, dict):
            for k, txt in items.items():
                c.addItem(txt, k)
        else:
            for k in items:
                c.addItem(str(k), k)
        c.currentIndexChanged.connect(lambda _i: self._set(key, cast(c.currentData())))
        c.setProperty("key", key)
        return c

    def _check(self, text: str, key: str, tip: str = "") -> QCheckBox:
        c = QCheckBox(text)
        c.setToolTip(tip)
        c.toggled.connect(lambda b: self._set(key, b))
        c.setProperty("key", key)
        return c

    def _build_graphics(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("Image quality")
        f = QFormLayout(g)
        self.ctl["resolution_scale"] = self._combo({s: f"{s}%  (~{int(1080 * s / 100)}p internal)"
                                                    for s in profile.RESOLUTION_SCALES}, "resolution_scale", int)
        f.addRow("Resolution", self.ctl["resolution_scale"])
        self.ctl["aa"] = self._combo(profile.AA_MODES, "aa")
        f.addRow("Anti-aliasing", self.ctl["aa"])
        self.ctl["upscaler"] = self._combo(profile.UPSCALERS, "upscaler")
        f.addRow("Output scaling", self.ctl["upscaler"])
        cas = QSlider(Qt.Orientation.Horizontal)
        cas.setRange(0, 100)
        cas.valueChanged.connect(lambda n: self._set("cas_sharpening", n))
        self.ctl["cas_sharpening"] = cas
        f.addRow("FSR sharpening", cas)
        self.ctl["anisotropic"] = self._combo({0: "Auto (game)", 2: "2x", 4: "4x", 8: "8x", 16: "16x"}, "anisotropic", int)
        f.addRow("Anisotropic filter", self.ctl["anisotropic"])
        self.ctl["aspect"] = self._combo({k: k for k in profile.ASPECTS}, "aspect")
        f.addRow("Aspect ratio", self.ctl["aspect"])
        self.ctl["output_resolution"] = self._combo(profile.OUTPUT_RESOLUTIONS, "output_resolution")
        f.addRow("PS3 output", self.ctl["output_resolution"])
        b = QPushButton("Handheld 800p preset (Steam Deck / 1280x800)")
        b.setToolTip("720p output, 16:10 aspect, 100 % + FSR upscaling to the 800p screen, lighter effects.")
        b.clicked.connect(self.apply_handheld_preset)
        f.addRow("", b)
        self.ctl["shadows"] = self._combo(profile.SHADOWS, "shadows")
        f.addRow("Shadows", self.ctl["shadows"])
        self.ctl["motion_blur"] = self._combo(profile.MOTION_BLUR, "motion_blur")
        f.addRow("Motion blur", self.ctl["motion_blur"])
        self.ctl["depth_of_field"] = self._check("Depth of field", "depth_of_field")
        f.addRow("", self.ctl["depth_of_field"])
        glare = QDoubleSpinBox()
        glare.setRange(0, 2)
        glare.setSingleStep(0.1)
        glare.valueChanged.connect(lambda x: self._set("lamp_glare", round(x, 2)))
        self.ctl["lamp_glare"] = glare
        f.addRow("Lamp glare (1 = stock)", glare)
        self.gfx_hint = label("", 9, name="muted")
        f.addRow("", self.gfx_hint)
        v.addWidget(g)

        v.addWidget(self._build_color_grading())

        g = QGroupBox("Frame rate && display")
        f = QFormLayout(g)
        self.ctl["frame_mode"] = self._combo(profile.FRAME_MODES, "frame_mode")
        f.addRow("Frame rate", self.ctl["frame_mode"])
        self.ctl["unlock_menu_fps"] = self._check("60 FPS in Gallery / new-car screens (Unlock FPS patch)", "unlock_menu_fps")
        f.addRow("", self.ctl["unlock_menu_fps"])
        self.ctl["fullscreen"] = self._check("Fullscreen", "fullscreen")
        f.addRow("", self.ctl["fullscreen"])
        self.ctl["performance_overlay"] = self._check("Show RPCS3 performance overlay", "performance_overlay")
        f.addRow("", self.ctl["performance_overlay"])
        f.addRow("", label("GT6 runs its simulation at 60 Hz, so above 60 FPS the game would run too fast. "
                           "60 FPS that holds steady matters more for racing.", 9, name="muted"))
        v.addWidget(g)

        g = QGroupBox("Camera (Extended FOV patch, 0 = stock)")
        f = QFormLayout(g)
        for key, txt in (("fov_bumper", "Bumper"), ("fov_cockpit", "Cockpit"), ("fov_roof", "Roof/Hood"), ("fov_chase", "Chase")):
            sp = QSpinBox()
            sp.setRange(0, 150)
            sp.valueChanged.connect(lambda n, k=key: self._set(k, n))
            self.ctl[key] = sp
            f.addRow(f"{txt} vertical FOV", sp)
        v.addWidget(g)

        g = QGroupBox("Emulation")
        f = QFormLayout(g)
        self.ctl["gpu_adapter"] = QComboBox()
        self.ctl["gpu_adapter"].currentIndexChanged.connect(lambda _i: self._set("gpu_adapter", self.ctl["gpu_adapter"].currentData() or ""))
        f.addRow("GPU", self.ctl["gpu_adapter"])
        self.ctl["render_path"] = self._combo(profile.RENDER_PATHS, "render_path")
        f.addRow("Render path", self.ctl["render_path"])
        self.ctl["spu_block_size"] = self._combo(profile.SPU_BLOCK, "spu_block_size")
        self.ctl["spu_block_size"].setToolTip("Changing this recompiles all SPU code on the next start (several minutes).")
        f.addRow("SPU block size", self.ctl["spu_block_size"])
        f.addRow("", label("Changing SPU block size triggers a full SPU recompile on the next start.", 9, name="muted"))
        self.ctl["thread_scheduler"] = self._combo(profile.SCHEDULERS, "thread_scheduler")
        f.addRow("Thread scheduler", self.ctl["thread_scheduler"])
        for key, txt, tip in (
            ("zcull_queries_disabled", "Disable ZCull occlusion queries",
             "Fixes reward-screen slowdowns and Garage car-image softlocks; may crackle audio in bumper cam."),
            ("accurate_rsx_reservation", "Accurate RSX reservation access", "Fewer RSX desyncs (recommended)."),
            ("multithreaded_rsx", "Multithreaded RSX", "Causes vertex explosions on cars in GT6 - keep off."),
            ("handle_tiled_memory", "Handle RSX memory tiling",
             "Fixes coloured noise over driver names / HUD text in races (recommended)."),
            ("async_texture_streaming", "Asynchronous texture streaming", ""),
            ("audio_time_stretch", "Audio time stretching", "Smoother audio when the game slows down."),
            ("use_gamemode", "Feral GameMode", ""),
            ("use_mangohud", "MangoHud overlay", ""),
        ):
            self.ctl[key] = self._check(txt, key, tip)
            f.addRow("", self.ctl[key])
        b = QPushButton("Reset to recommended")
        b.clicked.connect(self.reset_profile)
        f.addRow("", b)
        v.addWidget(g)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ patches tab
    CG_LABELS = {
        "cg_brightness": ("Brightness", "Flat offset: lifts or lowers the whole image."),
        "cg_contrast": ("Contrast", "Stretches the image around mid-grey."),
        "cg_gamma": ("Gamma (midtones)", "Positive brightens midtones without touching black and white."),
        "cg_shadows": ("Shadows", "Raises (positive) or crushes (negative) the black level."),
        "cg_highlights": ("Highlights", "Scales the bright end of the image."),
        "cg_saturation": ("Saturation", "-100 = black and white, +100 = twice as colourful."),
        "cg_vibrance": ("Vibrance", "Boosts muted colours more than already strong ones (skin, sky)."),
        "cg_temperature": ("Temperature", "Negative = cooler / bluer, positive = warmer / more orange."),
        "cg_tint": ("Tint", "Negative = greener, positive = more magenta."),
        "cge_gain_r": ("GT6 gain - red", "Scales the red GT6's own color correction outputs (per track look kept)."),
        "cge_gain_g": ("GT6 gain - green", "Scales GT6's own green output."),
        "cge_gain_b": ("GT6 gain - blue", "Scales GT6's own blue output."),
        "cge_bias_r": ("GT6 bias - red", "Adds to / subtracts from red after GT6's gain."),
        "cge_bias_g": ("GT6 bias - green", "Adds to / subtracts from green after GT6's gain."),
        "cge_bias_b": ("GT6 bias - blue", "Adds to / subtracts from blue after GT6's gain."),
        "cge_gamma_r": ("GT6 gamma - red", "Positive brightens red midtones in GT6's own gamma stage."),
        "cge_gamma_g": ("GT6 gamma - green", "Positive brightens green midtones."),
        "cge_gamma_b": ("GT6 gamma - blue", "Positive brightens blue midtones."),
        "cge_chroma": ("GT6 chroma", "GT6's own saturation: -100 = black and white, +100 = double."),
    }

    def _grading_slider(self, f: QFormLayout, key: str) -> None:
        text, tip = self.CG_LABELS[key]
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(-100, 100)
        sl.setSingleStep(1)
        sl.setPageStep(10)
        sl.setToolTip(tip + "  Click the number to reset it.")
        val = QPushButton("0")
        val.setFlat(True)
        val.setFixedWidth(44)
        val.setToolTip("Reset to 0")
        sl.valueChanged.connect(lambda n, b=val: b.setText(f"{n:+d}" if n else "0"))
        sl.valueChanged.connect(lambda n, k=key: self._set(k, n))
        val.clicked.connect(lambda _c=False, s=sl: s.setValue(0))
        h.addWidget(sl, 1)
        h.addWidget(val)
        self.ctl[key] = sl
        f.addRow(text, row)

    def _build_color_grading(self) -> QGroupBox:
        g = QGroupBox("Color grading")
        f = QFormLayout(g)
        self.ctl["color_grading"] = self._check(
            "Enable color grading", "color_grading",
            "Applied by the GT6-patched emulator to the final image, after upscaling. "
            "The emulator's own menus and overlays are not affected.")
        f.addRow("", self.ctl["color_grading"])
        for key in profile.COLOR_GRADING:
            self._grading_slider(f, key)
        self.ctl["cg_dither"] = self._check(
            "Dither (hides colour banding from strong adjustments)", "cg_dither")
        f.addRow("", self.ctl["cg_dither"])
        f.addRow("", label("GT6's own color correction (EU 1.22, experimental): adjusts the grade GT6 applies per "
                           "track instead of the final image. Turns on the 'Engine Color Correct' game patch.",
                           9, name="muted"))
        self.ctl["engine_color"] = self._check("Adjust GT6's own color correction", "engine_color",
                                               "Only has an effect in scenes where GT6 uses its color correction.")
        f.addRow("", self.ctl["engine_color"])
        for key in profile.ENGINE_COLOR:
            self._grading_slider(f, key)
        b = QPushButton("Reset color grading")
        b.clicked.connect(self.reset_color_grading)
        f.addRow("", b)
        f.addRow("", label("Also adjustable live while you play: open the home menu (Xbox / PS button or F10) -> "
                           "Settings -> Color (the mouse works there too). Press Save to keep the values; the "
                           "launcher picks them up after the game closes. The final-image grading and the live "
                           "sliders need the GT6-patched emulator (patches 09 and 10); GT6's own color correction "
                           "also works with older builds, set from here.", 9, name="muted"))
        return g

    def reset_color_grading(self) -> None:
        for key in profile.GRADING_SLIDERS:
            self.ctl[key].setValue(0)
        self.ctl["cg_dither"].setChecked(True)

    def _build_patches(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        top = QHBoxLayout()
        self.patch_info = label("", 9, name="muted")
        top.addWidget(self.patch_info, 1)
        b = QPushButton("Update patch databases")
        b.clicked.connect(self.update_patches)
        top.addWidget(b)
        v.addLayout(top)
        split = QSplitter(Qt.Orientation.Vertical)
        self.patch_list = QListWidget()
        self.patch_list.itemChanged.connect(self._on_patch_toggled)
        self.patch_list.currentItemChanged.connect(self._on_patch_selected)
        split.addWidget(self.patch_list)
        self.patch_detail = QWidget()
        self.patch_detail_l = QVBoxLayout(self.patch_detail)
        split.addWidget(scroll(self.patch_detail))
        split.setSizes([420, 200])
        v.addWidget(split, 1)
        v.addWidget(label("Ticked = applied at boot. Patches driven by the Graphics/LAN tabs are ticked automatically; "
                          "ticking or unticking here overrides them.", 9, name="muted"))
        return w

    # ------------------------------------------------------------------ mods tab
    def _build_mods(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        g = QGroupBox("GT6 Career Mod (+ Spec II mod)")
        f = QVBoxLayout(g)
        f.addWidget(label("By Lunard, based on Spec II Beta 7 (Nenkai, TheAdmiester), with features from Strato mod "
                          "(Emivebe) and Performance mod (Plunke). Requires game version 1.22.", 9, name="muted"))
        self.mod_lbl = label()
        f.addWidget(self.mod_lbl)
        h = QHBoxLayout()
        b = QPushButton("Download from GTPlanet")
        b.setObjectName("accent")
        b.clicked.connect(self.get_career_mod)
        h.addWidget(b)
        b = QPushButton("Import archive...")
        b.clicked.connect(self.import_mod)
        h.addWidget(b)
        h.addStretch(1)
        f.addLayout(h)
        h = QHBoxLayout()
        self.mod_install_btn = QPushButton("Install Spec II + Career mod")
        self.mod_install_btn.clicked.connect(self.install_mods)
        h.addWidget(self.mod_install_btn)
        self.mod_remove_btn = QPushButton("Uninstall all mods (restore original)")
        self.mod_remove_btn.clicked.connect(self.uninstall_mods)
        h.addWidget(self.mod_remove_btn)
        h.addStretch(1)
        f.addLayout(h)
        f.addWidget(label("Every file a mod overwrites is backed up, so uninstalling restores the game exactly. "
                          "Start a new save when you first use the Career mod.", 9, name="muted"))
        v.addWidget(g)
        g = QGroupBox("Cheats (single player)")
        f = QVBoxLayout(g)
        self.ctl["dev_menu"] = self._check("Enable GT6's developer menu (credits, cars) - game version 1.22", "dev_menu")
        f.addWidget(self.ctl["dev_menu"])
        f.addWidget(label("In the game, at My Home: hold R1 and press SELECT (your pad: hold RB, press the "
                          "View/Back button; keyboard: hold E, then hold Space ~1 s).\n"
                          "- Cashier: move the slider to the amount you want (steps of Cr. 100,000) and press Exec "
                          "- this SETS your credits to that amount.\n"
                          "- Garage: add cars at random.\n"
                          "Save afterwards. Never use Misc -> Delete Save Data in that menu. Not for online play.\n"
                          "While on, the race pause menu also shows the developer-only 'Force finish' button; "
                          "its label reads 'caption_FORCE_FINISH' because the game has no text for it.",
                          9, name="muted"))
        v.addWidget(g)
        g = QGroupBox("Mod readme")
        f = QVBoxLayout(g)
        self.mod_readme = QPlainTextEdit()
        self.mod_readme.setReadOnly(True)
        self.mod_readme.setMinimumHeight(260)
        f.addWidget(self.mod_readme)
        v.addWidget(g)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ LAN tab
    def _build_lan(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        g = QGroupBox("LAN mode")
        f = QFormLayout(g)
        self.ctl["lan_enabled"] = self._check("Enable LAN play (boots with 'lanmode', no PSN needed)", "lan_enabled")
        f.addRow("", self.ctl["lan_enabled"])
        self.lan_status = label()
        f.addRow("Status", self.lan_status)
        self.user_edit = QLineEdit()
        self.user_edit.setMaxLength(16)
        self.user_edit.editingFinished.connect(lambda: (lan.set_username(self.user_edit.text()), self.refresh()))
        f.addRow("Player name", self.user_edit)
        h = QHBoxLayout()
        self.psid_lbl = label("", 9)
        h.addWidget(self.psid_lbl, 1)
        b = QPushButton("New PSID")
        b.clicked.connect(lambda: (lan.regenerate_psid(), self.refresh()))
        h.addWidget(b)
        f.addRow("Console PSID", h)
        self.bind_edit = QLineEdit()
        self.bind_edit.editingFinished.connect(lambda: self._set("lan_bind_address", self.bind_edit.text().strip() or "0.0.0.0"))
        f.addRow("Bind address", self.bind_edit)
        self.ip_lbl = label()
        f.addRow("This PC", self.ip_lbl)
        v.addWidget(g)
        g = QGroupBox("Online (community server, EU disc 1.22 only)")
        f = QVBoxLayout(g)
        self.ctl["online_enabled"] = self._check("Enable online via the community GT6 server (irekej patch)", "online_enabled")
        f.addWidget(self.ctl["online_enabled"])
        f.addWidget(label("Uses the community 'irekej' GT6 server through the RPCN network. Enter your RPCN "
                          "account below (stored like RPCS3 does: the password is only kept as a hash). "
                          "LAN mode takes priority when both are ticked.", 9, name="muted"))
        rf = QFormLayout()
        self.rpcn_user = QLineEdit()
        self.rpcn_pass = QLineEdit()
        self.rpcn_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.rpcn_pass.setPlaceholderText("unchanged")
        self.rpcn_token = QLineEdit()
        self.rpcn_token.setPlaceholderText("from the RPCN e-mail (if your account needs it)")
        rf.addRow("RPCN user", self.rpcn_user)
        rf.addRow("Password", self.rpcn_pass)
        rf.addRow("Token", self.rpcn_token)
        f.addLayout(rf)
        b = QPushButton("Save RPCN login")
        b.clicked.connect(self.save_rpcn)
        f.addWidget(b)
        v.addWidget(g)
        g = QGroupBox("How to race over LAN")
        f = QVBoxLayout(g)
        f.addWidget(label(lan.HOWTO, 9))
        v.addWidget(g)
        if lan.firewall_active():  # only bother people whose firewall would actually block LAN races
            g = QGroupBox("Firewall")
            f = QVBoxLayout(g)
            f.addWidget(label(lan.FIREWALL_HELP["windows" if paths.IS_WINDOWS else "linux"], 9))
            v.addWidget(g)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ advanced/log
    def _build_advanced(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        g = QGroupBox("Tools")
        f = QVBoxLayout(g)
        for txt, fn in (("Open launcher data folder", lambda: self._open(paths.data_dir())),
                        ("Open emulator log (for bug reports)", lambda: self._open(paths.rpcs3_log_file()))):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            f.addWidget(b)
        v.addWidget(g)
        g = QGroupBox("Danger zone")
        f = QVBoxLayout(g)
        b = QPushButton("Reset game data (removes installed updates and mods, keeps saves)")
        b.clicked.connect(self.reset_game_data)
        f.addWidget(b)
        v.addWidget(g)
        g = QGroupBox("Troubleshooting")
        f = QVBoxLayout(g)
        f.addWidget(label("- Stuck at the Sony Computer Entertainment logo: delete GT6's save data "
                          "(RPCS3 -> Manage -> Save Data).\n"
                          "- Black 3D world on 1.06+: Render path must use color buffers (Automatic does this).\n"
                          "- Garage softlock while updating car pictures: keep 'Disable ZCull occlusion queries' on.\n"
                          "- Spiky black car bodies: turn Multithreaded RSX off.\n"
                          "- First start of a version takes minutes (PPU/SPU caches compile) - later starts are fast.", 9))
        v.addWidget(g)
        g = QGroupBox("About")
        f = QVBoxLayout(g)
        f.addWidget(label(f"Data: {paths.data_dir()}\nRPCS3 config: {paths.rpcs3_config_dir()}", 9, name="muted"))
        f.addWidget(label("Patches: AlexHaust (granturismo-RPCS3-patches), RPCS3 patch database (Develop Settings: "
                          "Nenkai/OpenAdhoc, illusion), LAN fixes from abowen's GT6 LAN gist. "
                          "You need your own copy of the game.", 9, name="muted"))
        v.addWidget(g)
        v.addStretch(1)
        return w

    def _build_log(self) -> QWidget:
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("monospace", 9))
        return self.log_view

    # ------------------------------------------------------------------ logging
    def _log_threadsafe(self, s: str) -> None:
        holder = getattr(self, "_logsig_holder", None)
        if holder:
            holder.line.emit(str(s))
        else:
            print(s)

    def _append_log(self, s: str) -> None:
        self.log_view.appendPlainText(s.rstrip())

    # ------------------------------------------------------------------ settings binding
    def _set(self, key: str, value) -> None:
        if self._loading:
            return
        setattr(self.s, key, value)
        self._save_soon()
        if key == "lan_enabled":
            self._loading = True
            self.lan_quick.setChecked(value)
            self.ctl["lan_enabled"].setChecked(value)
            self._loading = False
        self._update_hints()
        if key in ("aa", "aspect", "motion_blur", "depth_of_field", "shadows", "lamp_glare", "unlock_menu_fps",
                   "resolution_scale", "lan_enabled", "online_enabled", "dev_menu", "engine_color")                 or key.startswith(("fov_", "cge_")):
            self._fill_patch_list()

    def _save_soon(self) -> None:
        """Coalesce rapid changes (slider drags) into one settings write."""
        t = getattr(self, "_save_timer", None)
        if t is None:
            t = self._save_timer = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(self.core.save)
        t.start(400)

    def _set_data(self, key: str, value) -> None:
        if self._loading:
            return
        self.core.data[key] = value
        self.core.save()

    def _load_settings_into_ui(self) -> None:
        self._loading = True
        try:
            for key, w in self.ctl.items():
                val = getattr(self.s, key, None)
                if isinstance(w, QComboBox):
                    i = w.findData(val)
                    if i >= 0:
                        w.setCurrentIndex(i)
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(val))
                elif isinstance(w, (QSpinBox, QSlider)):
                    w.setValue(int(val or 0))
                elif isinstance(w, QDoubleSpinBox):
                    w.setValue(float(val or 0))
            self.lan_quick.setChecked(self.s.lan_enabled)
            self.parallel_spin.setValue(int(self.core.data.get("parallel", 4)))
            self.delete_pkgs.setChecked(bool(self.core.data.get("delete_pkgs", False)))
            self.bind_edit.setText(self.s.lan_bind_address)
        finally:
            self._loading = False
        self._update_hints()

    def _update_hints(self) -> None:
        hints = []
        if self.s.aa == "off" and self.s.resolution_scale < 200:
            hints.append("No post AA: use 200% or more resolution, otherwise edges will shimmer.")
        if self.s.resolution_scale > 100 and self.s.motion_blur.startswith("gameplay"):
            hints.append("Known issue: motion blur can flash green/magenta above 100% resolution.")
        entry = self.current()
        cb, blit = profile.render_flags(self.s, entry.installed if entry else None)
        if cb and self.s.resolution_scale >= 250:
            hints.append("Heavy: 250-300% with color buffers (needed on 1.22) can drop FPS and make the audio "
                         "crackle. 100-150% is recommended for a steady 60 FPS.")
        if cb and self.s.resolution_scale > 100:
            hints.append("Color buffers are on (1.06+): resolution scaling relies on AlexHaust's res-scale fix "
                         "patches (enabled automatically); the game renders 1440x1080 internally at 100%.")
        if self.s.aspect != "16:9":
            hints.append("Ultrawide: 3D view is widened, HUD and menus stay 16:9.")
        self.gfx_hint.setText("\n".join(hints))
        self.ctl["cas_sharpening"].setEnabled(self.s.upscaler == "fsr")

    def apply_handheld_preset(self) -> None:
        for k, v in profile.HANDHELD_PRESET.items():
            setattr(self.s, k, v)
        self.core.save()
        self._load_settings_into_ui()
        self._fill_patch_list()

    # settings that 'Reset to recommended' (graphics / emulation) must not touch
    RESET_KEEP = ("lan_enabled", "lan_bind_address", "online_enabled", "extra_patches", "gpu_adapter",
                  "controller_mode", "controller_device", "wheel_enabled", "wheel_name", "wheel_mapping",
                  "console_language", "dev_menu", "fullscreen")

    def reset_profile(self) -> None:
        keep = {k: getattr(self.s, k) for k in self.RESET_KEEP}
        self.core.settings = self.s = profile.Settings.from_dict(keep)
        self.core.save()
        self._load_settings_into_ui()
        self._fill_pads()
        self._update_wheel_label()
        self._fill_patch_list()

    # ------------------------------------------------------------------ state refresh
    def current(self):
        tid = self.game_box.currentData()
        return next((g for g in self.core.games() if g.title_id == tid), None)

    def refresh(self) -> None:
        games = self.core.games()
        self._loading = True
        cur = self.core.data.get("active")
        self.game_box.clear()
        for g in games:
            self.game_box.addItem(f"{g.label}   (v{g.installed or g.image.disc_version})", g.title_id)
        i = self.game_box.findData(cur)
        self.game_box.setCurrentIndex(max(i, 0))
        self._loading = False
        entry = self.current()

        rp_path = self.core.rpcs3_path()
        if rp_path:
            self.build_lbl.setText("" if is_patched_build(rp_path) else STOCK_BUILD_WARNING)
        else:
            self.build_lbl.setText("Emulator component missing - reinstall the launcher." if not paths.IS_WINDOWS
                                   else "Preparing the emulator component...")
        fw_ok = bool(rp_path) and RPCS3(rp_path).firmware_installed()
        if fw_ok:
            self.fw_lbl.setText(f"Installed (version {RPCS3(rp_path).firmware_version() or '?'})")
            restyle(self.fw_lbl, "ok")
            self.fw_btn.setText("Reinstall firmware")
            restyle(self.fw_btn, "")
        else:
            self.fw_lbl.setText("Not installed")
            restyle(self.fw_lbl, "warn")
            self.fw_btn.setText("Install firmware")
            restyle(self.fw_btn, "accent")
        self.games_lbl.setText(wrap_path("\n".join(f"{g.label}: {g.image.path}" for g in games)) or "No game added yet.")
        restyle(self.games_lbl, "ok" if games else "warn")

        # updates
        self._loading = True
        self.target_box.clear()
        if entry:
            vers = updates.available_versions(entry.title_id)
            tags = {"01.22": "  - recommended: mods, LAN, online", "01.05": "  - best performance, no mods/LAN"}
            for ver in reversed(vers):
                size = sum(p.size for p in updates.chain(entry.title_id, ver, None))
                self.target_box.addItem(f"{ver}   ({updates.bytes_h(size)} download){tags.get(ver, '')}", ver)
            self.target_box.setCurrentIndex(max(self.target_box.findData(self.core.target_version(entry.title_id)), 0))
        self._loading = False
        self._on_target_changed(update_only=True)
        if entry:
            todo = updates.chain(entry.title_id, self.core.target_version(entry.title_id), entry.installed)
            size = sum(p.size for p in todo)
            if todo:
                self.upd_lbl.setText(f"Installed: {entry.installed or '01.00 (disc)'} - {len(todo)} updates to install "
                                     f"({updates.bytes_h(size)}).")
                restyle(self.upd_lbl, "warn")
            else:
                self.upd_lbl.setText(f"Installed: {entry.installed or '01.00'} - up to date.")
                restyle(self.upd_lbl, "ok")
        else:
            self.upd_lbl.setText("Add a game disc first.")

        # mods
        if entry:
            stack = mods.installed_stack(entry.title_id)
            staged = [m.name for m in mods.KNOWN_MODS if mods.staged(m.id)]
            lines = [f"Imported: {', '.join(staged) or 'nothing yet'}",
                     f"Installed: {', '.join(mods.mod_by_id(m).name for m in stack) or 'none'}"]
            if entry.installed != "01.22":
                lines.append("Needs game version 1.22.")
            elif not mods.game_data_ready(entry.title_id):
                lines.append("Start the game once (update data is unpacked on first boot), then install.")
            self.mod_lbl.setText("\n".join(lines))
            self.mod_install_btn.setEnabled(bool(staged) and entry.installed == "01.22" and not stack)
            self.mod_remove_btn.setEnabled(bool(stack))
        readme = os.path.join(paths.mods_dir(), "ReadMe - IMPORTANT.txt")
        if os.path.exists(readme) and not self.mod_readme.toPlainText():
            with open(readme, "r", errors="replace") as fh:
                self.mod_readme.setPlainText(fh.read())

        # LAN
        self.user_edit.setText(lan.get_username())
        r = lan.rpcn_get()
        if not self.rpcn_user.hasFocus():
            self.rpcn_user.setText(str(r.get("NPID", "")))
        if not self.rpcn_token.hasFocus():
            self.rpcn_token.setText(str(r.get("Token", "")))
        self.psid_lbl.setText(lan.get_psid() or "(created on first RPCS3 start)")
        self.ip_lbl.setText(", ".join(lan.local_ips()) or "?")
        if entry and lan.supported(entry.title_id, entry.installed):
            self.lan_status.setText(f"Ready for {entry.title_id} 1.22")
            restyle(self.lan_status, "ok")
        elif entry:
            why = "needs version 1.22" if entry.installed != "01.22" else \
                f"LAN patches are only verified for {', '.join(sorted(lan.SUPPORTED))} 1.22 so far"
            self.lan_status.setText(f"Not available: {why}")
            restyle(self.lan_status, "warn")

        # GPU list
        self._loading = True
        gp = self.ctl["gpu_adapter"]
        gp.clear()
        gp.addItem("Automatic (RPCS3 default)", "")
        for a in self.core.gpu_adapters():
            gp.addItem(a, a)
        gp.setCurrentIndex(max(gp.findData(self.s.gpu_adapter), 0))
        self._loading = False

        # left status
        if not entry:
            st = "Add your Gran Turismo 6 disc image in Setup."
        else:
            st = (f"{entry.image.title}  -  {GT6_TITLES.get(entry.title_id, '')}\n"
                  f"Version {entry.installed or '01.00 (no updates)'}")
            stack = mods.installed_stack(entry.title_id)
            if stack:
                st += "  -  mods: " + ", ".join(mods.mod_by_id(m).name for m in stack)
            if self.core.needs_compile(entry):
                st += "\nNext start compiles the game for your PC (several minutes, once)."
        self.status_lbl.setText(st)
        ready = bool(entry) and fw_ok and bool(rp_path)
        busy = self.job is not None
        self.play_btn.setEnabled(ready and not busy and self.proc is None)
        self.play_btn.setText("RUNNING" if self.proc else "PLAY")
        self._fill_patch_list()

    def _on_game_changed(self, _i) -> None:
        if self._loading:
            return
        tid = self.game_box.currentData()
        if tid:
            self.core.set_active(tid)
            self.refresh()

    def _on_target_changed(self, _i=None, update_only: bool = False) -> None:
        ver = self.target_box.currentData()
        self.target_hint.setText(updates.VERSION_PRESETS.get(ver, "") if ver else "")
        if self._loading or update_only or not ver:
            return
        entry = self.current()
        if entry:
            if entry.installed and ver < entry.installed:
                QMessageBox.information(self, "Updates", f"Version {entry.installed} is already installed - the "
                                        f"target can't be older. To go back to {ver}, use Advanced -> Reset game "
                                        "data first.")
                self.refresh()
                return
            self.core.set_target_version(entry.title_id, ver)
            self.refresh()

    # ------------------------------------------------------------------ patches list
    def _fill_patch_list(self) -> None:
        entry = self.current()
        self.patch_list.blockSignals(True)
        self.patch_list.clear()
        self.patch_list.blockSignals(False)
        if not entry:
            self.patch_info.setText("Add a game first.")
            return
        if self._patch_index is None:
            self.patch_info.setText("Loading patch index...")
            self._load_patch_index()
            return
        ver = entry.installed or "01.00"
        avail = self.core.available_patches(entry.title_id, ver, self._patch_index)
        # exactly what the launch will apply (LAN/online/dev menu gated per game)
        want = profile.desired_patches(self.core.effective_settings(entry.title_id, ver), ver)
        if not avail:
            self.patch_info.setText(f"No patches exist for {entry.title_id} v{ver}. Install updates (1.22) in Setup "
                                    f"- the patches target 1.22 and 1.05.")
            return
        self.patch_info.setText(f"{len(avail)} patches for {entry.title_id} v{ver}, {len([p for p in avail if p.name in want])} enabled.")
        self.patch_list.blockSignals(True)
        for p in sorted(avail, key=lambda p: (p.name not in want, p.name.lower())):
            it = QListWidgetItem(f"{p.name}    -  {p.author}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if p.name in want else Qt.CheckState.Unchecked)
            it.setToolTip(p.notes)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.patch_list.addItem(it)
        self.patch_list.blockSignals(False)

    def _load_patch_index(self) -> None:
        def work(job):
            for msg in patches.ensure_sources():
                job.log(msg)
            return patches.load_index()

        def done(idx):
            self._patch_index = idx
            self._fill_patch_list()
        self._run_bg(work, done)

    def _on_patch_toggled(self, it: QListWidgetItem) -> None:
        p = it.data(Qt.ItemDataRole.UserRole)
        on = it.checkState() == Qt.CheckState.Checked
        extra = dict(self.s.extra_patches or {})
        cur = extra.get(p.name, {})
        extra[p.name] = {"enabled": on, "values": cur.get("values", {})}
        # if the override now equals what the profile would do anyway, drop it
        entry = self.current()
        ver = entry.installed if entry else None
        eff = self.core.effective_settings(entry.title_id, ver) if entry else self.s
        base = profile.desired_patches(profile.Settings.from_dict({**eff.to_dict(), "extra_patches": {}}), ver)
        if (p.name in base) == on and not cur.get("values"):
            extra.pop(p.name, None)
        self.s.extra_patches = extra
        self.core.save()
        QTimer.singleShot(0, self._fill_patch_list)

    def _on_patch_selected(self, it: Optional[QListWidgetItem], _prev=None) -> None:
        while self.patch_detail_l.count():
            w = self.patch_detail_l.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not it:
            return
        p = it.data(Qt.ItemDataRole.UserRole)
        self.patch_detail_l.addWidget(label(p.name, 11, True))
        self.patch_detail_l.addWidget(label(f"{p.author}  -  {p.source}  -  patch v{p.patch_version}"
                                            + (f"  -  group: {p.group}" if p.group else ""), 9, name="muted"))
        self.patch_detail_l.addWidget(label(p.notes or "(no notes)", 9))
        if p.config:
            vals = (self.s.extra_patches or {}).get(p.name, {}).get("values", {})
            form = QFormLayout()
            for c in p.config:
                try:
                    cur = float(vals.get(c.name, c.default if c.default is not None else 0.0))
                except (TypeError, ValueError):
                    cur = 0.0
                if c.allowed:
                    w = QComboBox()
                    for k, val in c.allowed.items():
                        w.addItem(k, val)
                    w.setCurrentIndex(max(0, min(range(w.count()), key=lambda i: abs((w.itemData(i) or 0) - cur))))
                    w.currentIndexChanged.connect(lambda _i, w=w, c=c, p=p: self._set_patch_value(p, c.name, w.currentData()))
                else:
                    w = QDoubleSpinBox()
                    w.setDecimals(0 if "long" in c.type else 3)
                    w.setRange(c.min if c.min is not None else -1e6, c.max if c.max is not None else 1e6)
                    w.setValue(cur)
                    w.valueChanged.connect(lambda x, c=c, p=p: self._set_patch_value(p, c.name, x))
                form.addRow(c.name, w)
            box = QWidget()
            box.setLayout(form)
            self.patch_detail_l.addWidget(box)
        self.patch_detail_l.addStretch(1)

    def _set_patch_value(self, p, name: str, value: float) -> None:
        extra = dict(self.s.extra_patches or {})
        e = dict(extra.get(p.name, {}))
        e.setdefault("enabled", True)
        e["values"] = {**e.get("values", {}), name: float(value)}
        extra[p.name] = e
        self.s.extra_patches = extra
        self.core.save()

    # ------------------------------------------------------------------ jobs
    def _run(self, title: str, fn: Callable, done: Optional[Callable] = None) -> None:
        if self.job:
            QMessageBox.information(self, paths.APP_NAME, "Another task is still running.")
            return
        job = Job(fn)
        th = QThread(self)
        job.moveToThread(th)
        th.started.connect(job.run)
        job.progressed.connect(self._on_progress)
        job.logged.connect(self._append_log)

        def finish(res):
            self._end_job()
            self._append_log(f"[done] {title}")
            if done:
                done(res)
            self.refresh()

        def fail(msg):
            self._end_job()
            self._append_log(f"[failed] {title}: {msg}")
            if msg != "Cancelled":
                QMessageBox.warning(self, title, msg)
            self.refresh()

        relays = [_on_gui(job.done, finish, self), _on_gui(job.failed, fail, self)]
        th.finished.connect(th.deleteLater)
        relays.append(_on_gui(th.finished, lambda: [r.deleteLater() for r in relays], self))
        job.done.connect(th.quit)
        job.failed.connect(th.quit)
        self.job, self.thread = job, th
        self.progress.show()
        self.progress.setRange(0, 0)
        self.progress_lbl.setText(title)
        self.cancel_btn.show()
        self.play_btn.setEnabled(False)
        self._append_log(f"[start] {title}")
        th.start()

    def _run_bg(self, fn: Callable, done: Callable) -> None:
        """Small background task that doesn't block the UI or use the progress bar."""
        job = Job(fn)
        th = QThread(self)
        job.moveToThread(th)
        th.started.connect(job.run)
        relays = [_on_gui(job.done, done, self),
                  _on_gui(job.failed, lambda m: self._append_log(f"[bg failed] {m}"), self)]
        job.done.connect(th.quit)
        job.failed.connect(th.quit)
        th.finished.connect(th.deleteLater)
        self._bg = getattr(self, "_bg", []) + [(job, th)]

        def cleanup(pair=(job, th)):
            if pair in self._bg:
                self._bg.remove(pair)
            for r in relays:
                r.deleteLater()
        relays.append(_on_gui(th.finished, cleanup, self))
        th.start()

    def _end_job(self) -> None:
        self.job = None
        self.thread = None
        self.progress.hide()
        self.cancel_btn.hide()
        self.progress_lbl.setText("")

    def _on_progress(self, text: str, done, total) -> None:
        self.progress_lbl.setText(text)
        if total:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(1000 * done / total))
            if total > 1 << 20:
                self.progress_lbl.setText(f"{text}  {updates.bytes_h(done)} / {updates.bytes_h(total)}")
        else:
            self.progress.setRange(0, 0)

    def cancel_job(self) -> None:
        if self.job:
            self.job.cancel()
            self.progress_lbl.setText("Cancelling...")

    # ------------------------------------------------------------------ actions
    def _first_run(self) -> None:
        # only on a brand-new install: never overwrite an existing (tuned) profile
        if not self.core.data.get("screen_checked") and self.core.fresh_install:
            self.core.data["screen_checked"] = True
            scr = QApplication.primaryScreen()
            if scr:
                size = scr.size() * scr.devicePixelRatio()
                if (size.width(), size.height()) in ((1280, 800), (800, 1280)):  # Steam Deck & co.
                    self.apply_handheld_preset()
                    self._append_log("800p screen detected - handheld preset applied")
            self.core.save()
        if paths.IS_WINDOWS and not self.core.rpcs3_path():
            self._run("Preparing emulator", lambda job: self.core.ensure_rpcs3_windows(job.progress),
                      lambda _r: QTimer.singleShot(0, self._first_run))
            return
        if not self.core.games():
            def work(job):
                job.progress("Looking for Gran Turismo 6 disc images...", 0, 0)
                return self.core.scan_for_games()
            self._run("Scan for games", work, lambda found: self._append_log(f"found {len(found)} disc image(s)"))

    def pick_rpcs3(self) -> None:
        flt = "rpcs3.exe (rpcs3.exe)" if paths.IS_WINDOWS else "RPCS3 AppImage (*.AppImage *.appimage rpcs3);;All files (*)"
        f, _ = QFileDialog.getOpenFileName(self, "Choose RPCS3", os.path.expanduser("~"), flt)
        if f:
            self.core.data["rpcs3_path"] = f
            self.core.save()
            self.refresh()

    def pick_firmware(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "PS3 firmware", os.path.expanduser("~"), "PS3UPDAT.PUP (*.PUP *.pup)")
        if f:
            self.core.data["firmware_path"] = f
            self.core.save()
            self.install_firmware()

    def install_firmware(self) -> None:
        self._run("Install PS3 firmware", lambda job: self.core.ensure_firmware(job.progress))

    def _add_game(self, path: str) -> None:
        try:
            g = self.core.add_game(path)
            self.core.set_active(g.title_id)
            self._append_log(f"added {g.label}: {path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Add game", str(e))
        self.refresh()

    def pick_iso(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Gran Turismo 6 disc image", os.path.expanduser("~"), "Disc image (*.iso)")
        if f:
            self._add_game(f)

    def pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Folder containing PS3_GAME")
        if d:
            self._add_game(d)

    def scan_isos(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Folder to scan (cancel = default locations)")
        self._run("Scan for games", lambda job: self.core.scan_for_games([d] if d else None),
                  lambda found: self._append_log(f"found {len(found)} new disc image(s)"))

    def install_updates(self) -> None:
        entry = self.current()
        if not entry:
            return
        if not RPCS3(self.core.rpcs3_path() or "").firmware_installed():
            QMessageBox.information(self, "Updates", "Install the PS3 firmware first.")
            return

        def work(job):
            dl = updates.Downloader(parallel=int(self.core.data.get("parallel", 4)), progress=job.progress, log=job.log)
            job.downloader = dl
            return self.core.install_updates(entry.title_id, job.progress, downloader=dl)
        self._run(f"Install updates for {entry.title_id}", work,
                  lambda v: QMessageBox.information(self, "Updates", f"Game is now at version {v}.\n\n"
                                                    "Start it once and wait for the main menu - it unpacks the "
                                                    "update data.\n\n" + self.core.COMPILE_NOTICE + "\n\n" + self.core.FIRST_122_NOTICE))

    def update_patches(self) -> None:
        def work(job):
            job.progress("Downloading patch databases", 0, 0)
            return patches.update_sources()

        def done(res):
            self._patch_index = None
            QMessageBox.information(self, "Patches", "\n".join(res))
        self._run("Update patches", work, done)

    def get_career_mod(self) -> None:
        def work(job):
            existing = mods.find_archive_in(os.path.expanduser("~/Downloads")) or mods.find_archive_in(paths.downloads_dir("mods"))
            src = existing or mods.try_download_career(job.progress)
            if not src:
                return None
            return mods.stage_download(src, job.progress)

        def done(found):
            if found is None:
                QDesktopServices.openUrl(QUrl(mods.CAREER_PAGE))
                QMessageBox.information(self, "Career mod",
                                        "GTPlanet only allows the download from a browser. The page is now open - "
                                        "click Download, then press 'Download from GTPlanet' here again "
                                        "(the archive is picked up from your Downloads folder automatically).")
                return
            self._append_log(f"mods ready: {', '.join(found)}")
            self.mod_readme.clear()
        self._run("Get GT6 Career Mod", work, done)

    def import_mod(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Mod archive", os.path.expanduser("~/Downloads"), "Zip archive (*.zip)")
        if f:
            self._run("Import mod", lambda job: mods.stage_download(f, job.progress),
                      lambda found: self._append_log(f"imported: {', '.join(found) or 'no known mod found'}"))

    def install_mods(self) -> None:
        entry = self.current()
        if not entry:
            return

        def work(job):
            n = 0
            for m in mods.KNOWN_MODS:  # dependency order
                if mods.staged(m.id) and m.id not in mods.installed_stack(entry.title_id):
                    n += mods.install(entry.title_id, m.id, job.progress)
            return n
        self._run("Install mods", work, lambda n: self._append_log(f"installed {n} mod files"))

    def uninstall_mods(self) -> None:
        entry = self.current()
        if not entry:
            return

        def work(job):
            out = []
            while mods.installed_stack(entry.title_id):
                out.append(mods.uninstall_top(entry.title_id, job.progress))
            return out
        self._run("Uninstall mods", work, lambda r: self._append_log(f"removed: {', '.join(r)}"))

    def write_config_only(self) -> None:
        entry = self.current()
        if entry:
            names = self.core.prepare(entry)
            QMessageBox.information(self, "Config", f"Written. Enabled patches:\n" + "\n".join(names))

    def reset_game_data(self) -> None:
        entry = self.current()
        if not entry:
            return
        if QMessageBox.question(self, "Reset", f"Delete installed updates and mods for {entry.title_id}?\n"
                                "Saves are kept. Downloaded update packages are kept.") \
                == QMessageBox.StandardButton.Yes:
            self.core.reset_game_data(entry.title_id)
            self.refresh()

    def save_rpcn(self) -> None:
        if not self.rpcn_user.text().strip():
            QMessageBox.information(self, "RPCN", "Enter your RPCN user name.")
            return
        try:
            lan.rpcn_set_login(self.rpcn_user.text(), self.rpcn_pass.text(), self.rpcn_token.text())
        except ValueError as e:
            QMessageBox.information(self, "RPCN", str(e))
            return
        self.rpcn_pass.clear()
        QMessageBox.information(self, "RPCN", "RPCN login saved.")

    def _open(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def play(self) -> None:
        entry = self.current()
        if not entry or self.proc:
            return
        if entry.installed is None and QMessageBox.question(
                self, "No updates", "The game has no updates installed (version 1.00). Start anyway?") \
                != QMessageBox.StandardButton.Yes:
            return
        if self.core.needs_compile(entry):
            box = QMessageBox(self)
            box.setWindowTitle("First start")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(self.core.startup_notice(entry))
            box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if box.exec() != QMessageBox.StandardButton.Ok:
                return
        try:
            self.proc = self.core.launch(entry)
            self._proc_entry = entry
            self._proc_started = __import__("time").time()
            self._append_log(f"started {entry.title_id} (pid {self.proc.pid})")
        except Exception as e:  # noqa: BLE001
            self._append_log(traceback.format_exc())
            QMessageBox.warning(self, "Start", str(e))
        self.refresh()

    def _poll_proc(self) -> None:
        if self.proc and self.proc.poll() is not None:
            self._append_log(f"game exited (code {self.proc.returncode})")
            if __import__("time").time() - getattr(self, "_proc_started", 0) > 180:
                self.core.mark_compiled(self._proc_entry)
            try:
                if self.core.sync_ingame_color_grading(self._proc_entry.title_id):
                    self._append_log("color grading: picked up the values saved in the in-game home menu")
                    self._load_settings_into_ui()
            except Exception:  # noqa: BLE001
                self._append_log(traceback.format_exc())
            self.proc = None
            self.refresh()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        QTimer.singleShot(0, lambda: _track_tabs_edge(self))

    def showEvent(self, e) -> None:
        super().showEvent(e)
        QTimer.singleShot(0, lambda: _track_tabs_edge(self))

    def closeEvent(self, e) -> None:
        if getattr(self, "_save_timer", None) and self._save_timer.isActive():
            self._save_timer.stop()
            self.core.save()
        if self.job:
            self.job.cancel()
            if self.thread:
                self.thread.quit()
                self.thread.wait(3000)
        super().closeEvent(e)


class WheelWizard(QDialog):
    """Records a wheel mapping: one control at a time, by moving/pressing it."""
    # (key, instruction, kind, optional)
    STEPS = [
        ("steering", "Turn the wheel to the RIGHT (about a quarter turn), then let it center.", "axis", False),
        ("throttle", "Press the ACCELERATOR pedal all the way down, then release.", "axis", False),
        ("brake", "Press the BRAKE pedal all the way down, then release.", "axis", False),
        ("clutch", "Press the CLUTCH pedal (Skip if you have none).", "axis", True),
        ("shift_up", "Pull the RIGHT paddle / shift-up button.", "button", True),
        ("shift_down", "Pull the LEFT paddle / shift-down button.", "button", True),
        ("cross", "Press the button you want as  X  (confirm / OK).", "button", False),
        ("circle", "Press the button you want as  O  (back).", "button", False),
        ("square", "Press the button you want as  [ ]  (Square).", "button", True),
        ("triangle", "Press the button you want as  /\\  (Triangle).", "button", True),
        ("pause", "Press the button you want as START (pause menu).", "button", False),
        ("select", "Press the button you want as SELECT (change view).", "button", True),
        ("up", "Press D-pad UP.", "button", True),
        ("down", "Press D-pad DOWN.", "button", True),
        ("left", "Press D-pad LEFT.", "button", True),
        ("right", "Press D-pad RIGHT.", "button", True),
        ("l2", "Press the button you want as L2 (look left / back).", "button", True),
        ("r2", "Press the button you want as R2 (look right).", "button", True),
        ("ps", "Press the button you want as the PS / Home button.", "button", True),
        ("shifter_1", "H-shifter: put it in 1st gear (Skip if you have no shifter - skips all gears).", "button", True),
        ("shifter_2", "H-shifter: 2nd gear.", "button", True),
        ("shifter_3", "H-shifter: 3rd gear.", "button", True),
        ("shifter_4", "H-shifter: 4th gear.", "button", True),
        ("shifter_5", "H-shifter: 5th gear.", "button", True),
        ("shifter_6", "H-shifter: 6th gear.", "button", True),
        ("shifter_r", "H-shifter: reverse.", "button", True),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        from . import gamepad
        self.gp = gamepad
        self.js = gamepad.Joysticks()
        self.setWindowTitle("Racing wheel set-up")
        self.setMinimumWidth(560)
        self.mapping: dict = {}
        self.wheel_name = ""
        self.used: set = set()
        v = QVBoxLayout(self)
        self.devices_lbl = label("", 9, name="muted")
        v.addWidget(self.devices_lbl)
        self.step_lbl = label("", 9, name="muted")
        v.addWidget(self.step_lbl)
        self.instr = label("", 13, True)
        self.instr.setMinimumHeight(70)
        v.addWidget(self.instr)
        self.status = label("", 10, name="ok")
        v.addWidget(self.status)
        h = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._back)
        h.addWidget(self.back_btn)
        h.addStretch(1)
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self._skip)
        h.addWidget(self.skip_btn)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        h.addWidget(cancel)
        v.addLayout(h)
        self.i = 0
        self.phase = "arm"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self._start_step()
        self.timer.start(25)

    def _start_step(self) -> None:
        names = [d["name"] + ("  (wheel)" if d["is_wheel"] else "") for d in self.js.devices]
        self.devices_lbl.setText("Detected: " + (", ".join(names) or "no controllers - connect your wheel"))
        if self.i >= len(self.STEPS):
            self._finish()
            return
        key, text, kind, optional = self.STEPS[self.i]
        self.step_lbl.setText(f"Step {self.i + 1} of {len(self.STEPS)}")
        self.instr.setText(text)
        self.status.setText("")
        self.skip_btn.setEnabled(optional)
        self.back_btn.setEnabled(self.i > 0)
        self.phase = "settle"
        self.settle_until = __import__("time").time() + 0.4
        self.base = None

    def _poll(self) -> None:
        import time
        if not self.js.devices:
            self._rescan = getattr(self, "_rescan", 0) + 1
            if self._rescan % 40 == 1:  # about once a second (timer runs every 25 ms)
                self.js.refresh()
            if not self.js.devices:
                self.devices_lbl.setText("Detected: no controllers - connect your wheel")
                return
            self._start_step()  # device appeared: show it and take a fresh baseline
            return
        now = self.js.state()
        if self.phase == "settle":  # wait until the previous control is released, then take a baseline
            if time.time() >= self.settle_until:
                self.base, self.phase = now, "wait"
            return
        if self.phase == "release":
            if self.gp.detect_change(self.base, now, self.js.devices, "any") is None:
                self.i += 1
                self._start_step()
            return
        key, _text, kind, _opt = self.STEPS[self.i]
        hit = self.gp.detect_change(self.base, now, self.js.devices, kind, self.used)
        if not hit:
            return
        m = {"device_type_id": hit["device_type_id"], "type": hit["type"], "id": hit["id"], "hat": hit["hat"],
             "reverse": False}
        if hit["type"] == "axis":
            # steering: turning right must increase; pedals: pressed must increase (released = minimum)
            m["reverse"] = hit["moved"] < hit["rest"]
            self.used.add((hit["device_type_id"], "axis", hit["id"]))
        elif hit["type"] == "hat":
            self.used.add((hit["device_type_id"], "hat", hit["id"], hit["hat"]))
        else:
            self.used.add((hit["device_type_id"], "button", hit["id"]))
        self.mapping[key] = m
        if key == "steering":
            dev = next(d for d in self.js.devices if d["type_id"] == hit["device_type_id"])
            self.wheel_name = dev["name"]
        what = f"{hit['type']} {hit['id']}" + (f" {hit['hat']}" if hit["hat"] else "")
        self.status.setText(f"OK - {what}. Release it...")
        self.phase = "release"

    def _skip(self) -> None:
        key = self.STEPS[self.i][0]
        self.mapping.pop(key, None)
        if key == "shifter_1":  # no H-shifter: skip all gears
            self.i = next(j for j, s in enumerate(self.STEPS) if s[0] == "shifter_r") + 1
        else:
            self.i += 1
        self._start_step()

    def _back(self) -> None:
        if self.i > 0:
            self.i -= 1
            old = self.mapping.pop(self.STEPS[self.i][0], None)
            if old:
                self.used = {u for u in self.used if not (u[0] == old["device_type_id"] and u[1] == old["type"]
                                                          and u[2] == old["id"])}
            self._start_step()

    def _finish(self) -> None:
        self.timer.stop()
        self.accept()

    def done(self, r) -> None:
        self.timer.stop()
        try:
            self.js.close()
        except Exception:
            pass
        super().done(r)


class _NoWheelUnlessFocused(QObject):
    """Scrolling a page must not change combo boxes / spin boxes under the mouse
    (that silently changed the target update version)."""

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.Type.Wheel and isinstance(obj, (QComboBox, QSpinBox, QDoubleSpinBox, QSlider)) \
                and (isinstance(obj, QComboBox) or not obj.hasFocus()):
            w = obj.parentWidget()
            while w is not None and not isinstance(w, QScrollArea):
                w = w.parentWidget()
            if w is not None:  # scroll the page instead
                QApplication.sendEvent(w.verticalScrollBar(), ev)
            return True
        return False


class _LogBridge(QObject):
    line = Signal(str)


def _track_tabs_edge(win: "MainWindow") -> None:
    bg = win._bgw
    edge = win.tabs.mapTo(bg, win.tabs.rect().topLeft()).x() - 12
    if edge != bg.visible_right:
        bg.visible_right = edge
        bg.update()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(paths.APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    wheel_guard = _NoWheelUnlessFocused(app)
    app.installEventFilter(wheel_guard)
    w = MainWindow()
    w.show()
    return app.exec()
