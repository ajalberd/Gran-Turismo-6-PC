"""PySide6 user interface."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import traceback
from typing import Callable, Optional

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRectF, Qt, QThread, QTimer, QUrl, Signal, Slot
)
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QIcon, QImage, QLinearGradient, QMovie, QPainter
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from . import diagnostics, i18n, lan, mods, patches, paths, profile, updates
from .core import Core, GT6_TITLES
from .i18n import tr
from .rpcs3 import RPCS3, STOCK_BUILD_WARNING, installed_version, is_patched_build

# Game exit within this many seconds (code 0) with mods installed -> offer to uninstall them (#49).
QUICK_EXIT_SECONDS = 60
ACCENT = "#e0157a"
STYLE = f"""
* {{ color: #e9e9ee; font-size: 10pt; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans CN", "PingFang SC", sans-serif; }}
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
QLabel#update {{ color: #ffd27f; background: rgba(0,0,0,0.72); border: 1px solid #ffb347; border-radius: 6px; padding: 5px 8px; }}
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


class _UpdateCheck(QObject):
    """Asks GitHub for a newer launcher release on a worker thread."""
    found = Signal(object)

    def start(self) -> None:
        def run() -> None:
            from . import selfupdate
            self.found.emit(selfupdate.check())
        threading.Thread(target=run, name="launcher-update-check", daemon=True).start()


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


# --------------------------------------------------------------------------- easter egg


def play_sound(wav_path: str):
    """Play a short sound effect asynchronously across Windows, Linux, and macOS."""
    import shutil
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception:
            pass
    for cmd in ("pw-play", "paplay", "aplay", "ffplay", "mpv", "afplay"):
        if shutil.which(cmd):
            try:
                args = [cmd]
                if cmd == "ffplay":
                    args += ["-nodisp", "-autoexit", "-loglevel", "quiet"]
                elif cmd == "mpv":
                    args += ["--no-video"]
                args.append(wav_path)
                return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass


class EasterEggOverlay(QWidget):
    """Pop-up animated character with transparent alpha background."""

    def __init__(self, parent: QWidget, webp_path: str, wav_path: str, on_finished: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self._on_finished = on_finished
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")

        self.lbl = QLabel(self)
        self.lbl.setStyleSheet("background: transparent;")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.movie = QMovie(webp_path)
        self.lbl.setMovie(self.movie)

        w, h = 360, 300
        self.resize(w, h)
        self.lbl.resize(w, h)

        parent_w = parent.width()
        parent_h = parent.height()
        target_x = max(0, parent_w - w - 16)
        target_y = max(0, parent_h - h - 10)
        start_y = parent_h + 10

        self.move(target_x, start_y)
        self.show()
        self.raise_()

        # Spring pop-up from bottom
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(280)
        self._anim.setStartValue(QPoint(target_x, start_y))
        self._anim.setEndValue(QPoint(target_x, target_y))
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)

        play_sound(wav_path)
        self.movie.start()
        self._anim.start()

        # Auto-dismiss smoothly when audio/video finishes (~4.5s)
        QTimer.singleShot(4200, self._slide_down)

    def _slide_down(self) -> None:
        target_x = self.x()
        start_y = self.y()
        end_y = self.parentWidget().height() + 10
        self._anim_down = QPropertyAnimation(self, b"pos")
        self._anim_down.setDuration(320)
        self._anim_down.setStartValue(QPoint(target_x, start_y))
        self._anim_down.setEndValue(QPoint(target_x, end_y))
        self._anim_down.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_down.finished.connect(self._cleanup)
        self._anim_down.start()

    def _cleanup(self) -> None:
        self.movie.stop()
        if self._on_finished:
            self._on_finished()
        self.deleteLater()


class _TabsEasterEggFilter(QObject):
    def __init__(self, win: "MainWindow"):
        super().__init__(win)
        self.win = win

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            bar = self.win.tabs.tabBar()
            pos = event.pos()
            corner_w = self.win.lang_btn.width() if hasattr(self.win, "lang_btn") else 110
            if obj is bar:
                last_idx = -1
                for i in range(bar.count() - 1, -1, -1):
                    if self.win.tabs.isTabVisible(i):
                        last_idx = i
                        break
                if last_idx >= 0:
                    tab_right = bar.tabRect(last_idx).right()
                    # Trigger in the empty bar area between last tab and language button
                    if tab_right < pos.x() < bar.width() - corner_w - 6:
                        self.win._play_easter_egg()
                        return True
            elif obj is self.win.tabs:
                last_idx = -1
                for i in range(bar.count() - 1, -1, -1):
                    if self.win.tabs.isTabVisible(i):
                        last_idx = i
                        break
                tab_right = bar.tabRect(last_idx).right() if last_idx >= 0 else 0
                if 0 <= pos.y() <= bar.height() + 8 and tab_right < pos.x() < self.win.tabs.width() - corner_w - 12:
                    self.win._play_easter_egg()
                    return True
        return super().eventFilter(obj, event)


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
        self._hardware_warning_shown = False
        self._last_direct_rpc_origin = ""
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

        # Hidden easter egg button in empty space between Log tab and language corner button
        self._egg_overlay: Optional[EasterEggOverlay] = None
        self.egg_btn = QPushButton("", self.tabs)
        self.egg_btn.setFixedSize(90, 32)
        self.egg_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.egg_btn.setStyleSheet("background: transparent; border: none;")
        self.egg_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.egg_btn.clicked.connect(self._play_easter_egg)
        self._egg_filter = _TabsEasterEggFilter(self)
        self.tabs.installEventFilter(self._egg_filter)
        self.tabs.tabBar().installEventFilter(self._egg_filter)

        # Language switch button in the top-right corner of the tab bar
        self.lang_btn = QPushButton(i18n.get_switch_button_label(self.s.ui_language))
        self.lang_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_btn.setToolTip("Switch language / 切换语言 / Changer de langue / 言語を切り替え")
        self.lang_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); "
            "border-radius: 6px; padding: 4px 10px; font-weight: 600; font-size: 9pt; color: #d6d6e2; margin-right: 6px; margin-top: 3px; } "
            "QPushButton:hover { background: rgba(255,255,255,0.18); border-color: rgba(255,255,255,0.28); color: white; }"
        )
        self.lang_btn.clicked.connect(self._cycle_language)
        self.tabs.setCornerWidget(self.lang_btn, Qt.Corner.TopRightCorner)

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
        self._record_original_texts()
        if self.s.ui_language != "en":
            self._retranslate_ui()
        else:
            self.refresh()
        self.poll = QTimer(self)
        self.poll.timeout.connect(self._poll_proc)
        self.poll.start(1000)
        self._check_external_rpcs3_launch()
        QTimer.singleShot(200, self._first_run)
        QTimer.singleShot(1500, self._start_update_check)

    def _start_update_check(self) -> None:
        self._update_check = _UpdateCheck(self)
        self._update_relay = _on_gui(self._update_check.found, self._show_update, self)
        self._update_check.start()

    def _show_update(self, rel) -> None:
        if not rel:
            return
        from html import escape
        from . import __version__
        kind = tr("beta") if rel.get("prerelease") else tr("release")
        self.update_lbl.setText(
            f'{tr("New launcher")} {kind} {escape(rel["tag"])} {tr("available")} - '
            f'<a style="color:#ffffff; font-weight:700;" href="{escape(rel["url"], quote=True)}">{tr("Download")}</a>')
        self.update_lbl.setToolTip(f'{tr("You have")} v{__version__}')
        self.update_lbl.setVisible(True)
        self._append_log(f"Launcher update available: {rel['tag']} (you have {__version__}) - {rel['url']}")

    # ------------------------------------------------------------------ left panel
    def _build_left(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(label("GRAN TURISMO 6", 26, True))
        from . import __version__
        self.version_lbl = label(f"{tr('PC edition  ·  v')}{__version__}", 11, False, "muted")
        v.addWidget(self.version_lbl)
        self.update_lbl = label("", 10, True, "update")
        self.update_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.update_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.update_lbl.setOpenExternalLinks(True)
        self.update_lbl.setVisible(False)
        v.addWidget(self.update_lbl)
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
        b = QPushButton("Keyboard keys")
        b.clicked.connect(self.show_keyboard_keys)
        h.addWidget(b)
        f.addLayout(h)
        self.pad_lbl = label("", 9, name="muted")
        f.addWidget(self.pad_lbl)
        f.addWidget(label("Automatic uses the first detected gamepad (Steam Deck, ROG Ally, Legion Go, MSI Claw, Xbox, PlayStation, 8BitDo...) "
                          "with standard button mapping; if none is detected, the current RPCS3 input setting is kept. "
                          "Choose Keyboard explicitly to switch to keyboard input. Racing-game style "
                          "triggers (RT accelerate, LT brake): in the game, Options -> Wireless Controller.", 9, name="muted"))
        h = QHBoxLayout()
        self.wheel_chk = QCheckBox(tr("Use racing wheel"))
        self.wheel_chk.toggled.connect(self._on_wheel_toggled)
        h.addWidget(self.wheel_chk)
        b = QPushButton(tr("Set up wheel..."))
        b.clicked.connect(self.setup_wheel)
        h.addWidget(b)
        self.invert_pedals_btn = QPushButton(tr("Invert pedals"))
        self.invert_pedals_btn.setToolTip(tr("Invert throttle, brake, and clutch pedal polarity if they act as pressed when released."))
        self.invert_pedals_btn.clicked.connect(self.invert_pedals)
        h.addWidget(self.invert_pedals_btn)
        self.reverse_ffb_chk = QCheckBox(tr("Reverse FFB"))
        self.reverse_ffb_chk.setToolTip(tr("Flip force feedback direction if the wheel snaps away from center or oscillates violently."))
        self.reverse_ffb_chk.toggled.connect(self._on_reverse_ffb_toggled)
        h.addWidget(self.reverse_ffb_chk)
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
        self.pad_box.addItem(tr("Automatic (first gamepad, else keyboard)"), ("auto", ""))
        for p in pads or []:
            tag = f" 🎮 [{tr('Handheld')}]" if gamepad.is_handheld_controller(p) else ""
            self.pad_box.addItem(f"{p}{tag}", ("pad", p))
        if self.s.controller_mode == "pad" and self.s.controller_device not in (pads or []):
            self.pad_box.addItem(f"{self.s.controller_device} {tr('(not connected)')}", ("pad", self.s.controller_device))
        self.pad_box.addItem(tr("Keyboard"), ("keyboard", ""))
        want = (self.s.controller_mode, self.s.controller_device if self.s.controller_mode == "pad" else "")
        for i in range(self.pad_box.count()):
            if tuple(self.pad_box.itemData(i)) == want:
                self.pad_box.setCurrentIndex(i)
        self._loading = False
        if pads is None:
            self.pad_lbl.setText(tr("Gamepad detection unavailable (SDL3 library not found)."))
        elif not pads:
            self.pad_lbl.setText(tr("No gamepad connected. Connect it (8BitDo: X-input mode) and click Refresh.")
                                 if paths.IS_WINDOWS else tr("No gamepad connected."))
        else:
            self.pad_lbl.setText(f"{tr('Connected:')} {', '.join(pads)}" if pads else tr("No gamepad connected."))

    def show_keyboard_keys(self) -> None:
        """Read-only table of the keyboard keys (#48); does not change any controller setting."""
        from html import escape
        from . import gamepad
        active, rows = gamepad.keyboard_key_table()
        body = "".join(f"<tr><td><b>{escape(key)}</b></td><td>{escape(tr(button))}</td><td>{escape(tr(action))}</td></tr>"
                       for button, key, action in rows)
        status = tr("Player 1 is set to Keyboard.") if active else \
            tr("Player 1 is a gamepad now. These keys work when Player 1 is set to Keyboard (or Automatic finds no gamepad).")
        box = QMessageBox(self)
        box.setWindowTitle(tr("Keyboard keys"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(f"<p>{escape(status)}</p>"
                    f"<table cellspacing='0' cellpadding='3'><tr><th align='left'>{escape(tr('Key'))}</th>"
                    f"<th align='left'>{escape(tr('PS3 button'))}</th><th align='left'>{escape(tr('In GT6'))}</th></tr>"
                    f"{body}</table>"
                    f"<p>{escape(tr('Letter keys need a Latin keyboard layout (e.g. English). With a Cyrillic or Greek layout active, switch to English while playing.'))}</p>")
        box.exec()

    def _on_pad_changed(self, _i) -> None:
        if self._loading:
            return
        mode, dev = self.pad_box.currentData()
        self.s.controller_mode, self.s.controller_device = mode, dev
        self.core.save()

    def _update_wheel_label(self) -> None:
        m = self.s.wheel_mapping or {}
        has_pedal_axes = any(
            isinstance(m.get(k), dict) and m[k].get("type") == "axis" for k in ("throttle", "brake", "clutch")
        )
        if hasattr(self, "invert_pedals_btn"):
            self.invert_pedals_btn.setEnabled(bool(has_pedal_axes))
        if m.get("steering"):
            n = len([k for k in m if m[k]])
            self.wheel_lbl.setText(f"{tr('Set up:')} {self.s.wheel_name or 'wheel'} ({n} controls mapped)")
        else:
            self.wheel_lbl.setText(tr("Not set up yet."))
        self._loading = True
        self.wheel_chk.setChecked(bool(self.s.wheel_enabled and m.get("steering")))
        if hasattr(self, "reverse_ffb_chk"):
            self.reverse_ffb_chk.setEnabled(bool(m.get("steering")))
            self.reverse_ffb_chk.setChecked(bool(self.s.wheel_reverse_ffb))
        self._loading = False

    def invert_pedals(self) -> None:
        """Flip the reverse flag for all mapped pedal axes to quickly resolve inverted pedals."""
        m = self.s.wheel_mapping or {}
        if not m:
            QMessageBox.information(self, tr("Racing wheel"), tr("No wheel mapping found. Please set up your wheel first."))
            return
        flipped = []
        for pedal in ("throttle", "brake", "clutch"):
            if pedal in m and isinstance(m[pedal], dict) and m[pedal].get("type") == "axis":
                m[pedal]["reverse"] = not m[pedal].get("reverse", False)
                status = tr("Inverted") if m[pedal]["reverse"] else tr("Normal")
                pedal_name = tr(pedal.capitalize())
                flipped.append(f"{pedal_name}: {status}")
        if not flipped:
            QMessageBox.information(self, tr("Racing wheel"), tr("No pedal axes found to invert."))
            return
        self.s.wheel_mapping = m
        self.core.save()
        on = bool(self.s.wheel_enabled and m.get("steering"))
        from . import gamepad
        gamepad.write_g27_config(m, on, ffb_device=int(m["steering"]["device_type_id"]) if on else 0,
                                 reverse_effects=self.s.wheel_reverse_ffb)
        self._update_wheel_label()
        QMessageBox.information(
            self,
            tr("Racing wheel"),
            tr("Pedal polarity updated:\n\n") + "\n".join(f"• {x}" for x in flipped)
        )

    def _on_reverse_ffb_toggled(self, on: bool) -> None:
        if self._loading:
            return
        self.s.wheel_reverse_ffb = on
        self.core.save()
        m = self.s.wheel_mapping or {}
        if m.get("steering"):
            from . import gamepad
            enabled = bool(self.s.wheel_enabled)
            gamepad.write_g27_config(m, enabled, ffb_device=int(m["steering"]["device_type_id"]) if enabled else 0,
                                     reverse_effects=on)

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
        opt_row = QHBoxLayout()
        self.auto_opt_btn = QPushButton("⚡ Auto-configure for my PC")
        self.auto_opt_btn.setToolTip(
            "Automatically detects your CPU, GPU, and RAM to set optimal graphics and emulation settings.")
        self.auto_opt_btn.clicked.connect(self.auto_configure_hardware)
        opt_row.addWidget(self.auto_opt_btn, 1)

        self.restore_opt_btn = QPushButton("Restore previous settings")
        self.restore_opt_btn.setToolTip(
            "Restore the settings you had before running auto-configuration.")
        self.restore_opt_btn.clicked.connect(self.restore_previous_settings)
        opt_row.addWidget(self.restore_opt_btn, 1)
        f.addRow("Presets", opt_row)

        self.handheld_preset_btn = QPushButton()
        self.handheld_preset_btn.setToolTip(
            "Apply the 800p handheld graphics preset. Press again to restore the graphics settings you had before.")
        self.handheld_preset_btn.clicked.connect(self.apply_handheld_preset)
        self._update_handheld_preset_button()
        self._update_auto_opt_buttons()
        f.addRow("", self.handheld_preset_btn)
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
        self.ctl["head_motion"] = self._check(
            "Cockpit head motion from G-forces (experimental)", "head_motion",
            "Moves the cockpit view with braking, acceleration and cornering using GT6's own neck model "
            "(normally used only for crashes). EU 1.22.")
        f.addRow("", self.ctl["head_motion"])
        sp = QSpinBox()
        sp.setRange(1, 20)
        sp.setSuffix(" x")
        sp.setToolTip("How strongly G-forces move the head (5 x is a good start).")
        sp.valueChanged.connect(lambda n: self._set("hm_strength", n))
        self.ctl["hm_strength"] = sp
        f.addRow("Head motion strength", sp)
        for key, txt, tip in (
                ("hm_braking", "  Braking / acceleration nod", "Head pitch from braking and acceleration."),
                ("hm_lean", "  Cornering lean (roll)", "Head tilt in corners."),
                ("hm_turn", "  Cornering turn (yaw)", "Head turn in corners."),
                ("hm_slide", "  Head slide", "Sideways and fore/aft head movement.")):
            sp = QSpinBox()
            sp.setRange(0, 300)
            sp.setSingleStep(10)
            sp.setSuffix(" %")
            sp.setToolTip(tip + " Percent of GT6's own amount; also adjustable live in the home menu "
                                "(Settings -> Head Motion).")
            sp.valueChanged.connect(lambda n, k=key: self._set(k, n))
            self.ctl[key] = sp
            f.addRow(txt, sp)
        v.addWidget(g)

        g = QGroupBox("Emulation")
        f = QFormLayout(g)
        self.ctl["gpu_adapter"] = QComboBox()
        self.ctl["gpu_adapter"].currentIndexChanged.connect(self._on_gpu_adapter_changed)
        f.addRow("GPU", self.ctl["gpu_adapter"])
        self.gpu_vram_warn = QLabel()
        self.gpu_vram_warn.setWordWrap(True)
        self.gpu_vram_warn.setVisible(False)
        restyle(self.gpu_vram_warn, "warn")
        f.addRow("", self.gpu_vram_warn)
        self.ctl["audio_format"] = self._combo(
            {"Stereo": "Stereo (2.0)", "Surround 5.1": "Surround 5.1"}, "audio_format")
        self.ctl["audio_format"].setToolTip(
            "5.1 requires a six-channel output device and operating-system speaker setup.")
        f.addRow("Audio output", self.ctl["audio_format"])
        self.ctl["render_path"] = self._combo(profile.RENDER_PATHS, "render_path")
        f.addRow("Render path", self.ctl["render_path"])
        ram_gb = profile.detect_system_ram_gb()
        ram_hint = f"Detected {ram_gb:.0f} GB RAM ({'Mega' if ram_gb >= 7.0 else 'Safe'} recommended). Changing recompiles SPU cache."
        self.ctl["spu_block_size"] = self._combo(profile.SPU_BLOCK, "spu_block_size")
        self.ctl["spu_block_size"].setToolTip(
            "Mega provides optimal performance and frame pacing for GT6 on systems with >= 8 GB RAM.\n"
            "Safe uses less compiler memory for systems under 8 GB RAM.\n"
            "Giga can cause thread deadlocks and audio desyncs in GT6."
        )
        f.addRow("SPU block size", self.ctl["spu_block_size"])
        f.addRow("", label(ram_hint, 9, name="muted"))
        self.ctl["thread_scheduler"] = self._combo(profile.SCHEDULERS, "thread_scheduler")
        f.addRow("Thread scheduler", self.ctl["thread_scheduler"])
        self.ctl["zcull_accuracy"] = self._combo(profile.ZCULL_ACCURACY, "zcull_accuracy")
        self.ctl["zcull_accuracy"].setToolTip(
            "Approximate is the standard fast default.\n"
            "Relaxed can resolve specific occlusion stalls.\n"
            "Precise forces exact PS3 occlusion query calculations, eliminating residual car or shadow flickering."
        )
        f.addRow("ZCULL accuracy", self.ctl["zcull_accuracy"])
        for key, txt, tip in (
            ("zcull_queries_disabled", "Disable ZCull occlusion queries",
             "Recommended - keep this on. Fixes 1-5 fps on the car delivery and part install screens and Garage car-image softlocks. Unticking it does not stop cars flickering on tracks like London. May crackle audio in bumper cam."),
            ("strict_rendering", "Strict rendering mode",
             "Forces strict pipeline synchronization for render targets. Fixes hood reflections showing previous frames (e.g. Ford Focus ST) and Racing Gear menu flickering, especially on AMD GPUs."),
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
        f.addWidget(label("Experimental: these mods do not work on every PC. If the game closes by itself right "
                          "after starting, click 'Uninstall all mods' - the launcher also offers this automatically.",
                          9, name="muted"))
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
        w = QWidget()
        v = QVBoxLayout(w)
        actions = QHBoxLayout()
        save = QPushButton("Save current logs")
        save.setToolTip("Save the current session's launcher and RPCS3 logs to a folder for bug reports.")
        save.clicked.connect(self._save_logs)
        actions.addWidget(save)
        actions.addStretch(1)
        v.addLayout(actions)
        v.addWidget(self.log_view)
        return w

    # ------------------------------------------------------------------ logging
    def _log_threadsafe(self, s: str) -> None:
        holder = getattr(self, "_logsig_holder", None)
        if holder:
            holder.line.emit(str(s))
        else:
            print(s)

    def _append_log(self, s: str) -> None:
        self.log_view.appendPlainText(s.rstrip())

    def _save_logs(self) -> None:
        from datetime import datetime
        base_dir = next((d for d in (os.path.expanduser("~/Desktop"), os.path.expanduser("~/Downloads"),
                                     os.path.expanduser("~")) if os.path.isdir(d)), os.path.expanduser("~"))
        default_name = f"gt6-logs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        dest, _ = QFileDialog.getSaveFileName(
            self, tr("Save current logs"), os.path.join(base_dir, default_name), "Zip archive (*.zip)"
        )
        if not dest:
            return
        try:
            zip_path, has_rpcs3 = diagnostics.save_logs_archive(
                dest, self.log_view.toPlainText(), settings=self.s, entry=self.current()
            )
        except OSError as e:
            QMessageBox.warning(self, tr("Save current logs"), f"{tr('Could not save logs:')} {e}")
            return
        included = "system-info.txt + launcher.log + RPCS3.log" if has_rpcs3 else "system-info.txt + launcher.log"
        box = QMessageBox(QMessageBox.Icon.Information, tr("Save current logs"),
                          f"{tr('Logs saved to:')}\n{zip_path}\n\n({included})",
                          QMessageBox.StandardButton.Ok, self)
        open_btn = box.addButton(tr("Open folder"), QMessageBox.ButtonRole.ActionRole)
        box.exec()
        if box.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(os.path.abspath(zip_path))))
        else:
            self._append_log("[logs saved] RPCS3 log was not available")

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
                   "resolution_scale", "lan_enabled", "online_enabled", "dev_menu", "engine_color", "head_motion")                 or key.startswith(("fov_", "cge_", "hm_")):
            self._fill_patch_list()

    def _on_gpu_adapter_changed(self, _i: int = 0) -> None:
        if self._loading:
            return
        adapter = self.ctl["gpu_adapter"].currentData() or ""
        self._set("gpu_adapter", adapter)
        self._update_gpu_warning(adapter)

    def _update_gpu_warning(self, adapter: str) -> None:
        if not hasattr(self, "gpu_vram_warn"):
            return
        effective = adapter
        if not effective:
            adapters = self.core.gpu_adapters()
            effective = adapters[0] if adapters else ""
        if not effective:
            self.gpu_vram_warn.setVisible(False)
            return

        is_low, msg = self.core.check_gpu_low_vram(effective)
        if is_low and msg:
            self.gpu_vram_warn.setText(f"⚠ {msg}")
            self.gpu_vram_warn.setVisible(True)
        else:
            self.gpu_vram_warn.setVisible(False)

    def _record_original_texts(self) -> None:
        """Stores the original English text for all UI elements so translation is lossless."""
        for gb in self.findChildren(QGroupBox):
            if not gb.property("orig_text"):
                gb.setProperty("orig_text", gb.title())
        for typ in (QPushButton, QCheckBox, QLabel):
            for w in self.findChildren(typ):
                if w is getattr(self, "lang_btn", None) or w is getattr(self, "egg_btn", None):
                    continue
                txt = w.text()
                if txt and not w.property("orig_text"):
                    w.setProperty("orig_text", txt)

    def _cycle_language(self) -> None:
        next_code, _ = i18n.next_language(self.s.ui_language)
        self.s.ui_language = next_code
        i18n.set_current_language(next_code)
        self.lang_btn.setText(i18n.get_switch_button_label(next_code))
        self._save_soon()
        self._retranslate_ui()

    def _lang_label(self, code: str) -> str:
        return i18n.get_switch_button_label(code)

    def _retranslate_ui(self) -> None:
        lang = self.s.ui_language
        i18n.set_current_language(lang)
        if hasattr(self, "lang_btn"):
            self.lang_btn.setText(i18n.get_switch_button_label(lang))
            self.lang_btn.setToolTip(f"{i18n.tr('Switch language', lang)} -> {i18n.get_switch_button_label(lang)}")

        # Re-translate group boxes
        for gb in self.findChildren(QGroupBox):
            orig = gb.property("orig_text")
            if orig:
                gb.setTitle(i18n.tr(orig, lang))

        # Re-translate buttons and checkboxes (excluding easter egg button)
        for typ in (QPushButton, QCheckBox):
            for btn in self.findChildren(typ):
                if btn is getattr(self, "lang_btn", None) or btn is getattr(self, "egg_btn", None):
                    continue
                orig = btn.property("orig_text")
                if orig:
                    btn.setText(i18n.tr(orig, lang))

        # Re-translate static labels
        for lbl in self.findChildren(QLabel):
            orig = lbl.property("orig_text")
            if orig:
                lbl.setText(i18n.tr(orig, lang))

        # Tab titles
        tab_keys = ["Setup", "Graphics", "Patches", "Mods", "LAN", "Advanced", "Log"]
        for idx, key in enumerate(tab_keys):
            if idx < self.tabs.count():
                self.tabs.setTabText(idx, i18n.tr(key, lang))

        # Log tab is hidden when Chinese is selected
        if self.tabs.count() > 6:
            self.tabs.setTabVisible(6, lang != "zh_CN")
            if lang == "zh_CN" and self.tabs.currentIndex() == 6:
                self.tabs.setCurrentIndex(0)

        # Subheader and Play button
        from . import __version__
        if hasattr(self, "version_lbl"):
            self.version_lbl.setText(f"{i18n.tr('PC edition  ·  v', lang)}{__version__}")
        if hasattr(self, "play_btn") and self.job is None and self.proc is None:
            self.play_btn.setText(i18n.tr("PLAY", lang))

        self._fill_pads()
        self._update_wheel_label()
        self.refresh()

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
        self._update_auto_opt_buttons()

    def _update_hints(self) -> None:
        hints = []
        if self.s.render_path == "cpu_blit" and self.s.resolution_scale > 100:
            hints.append(tr("Force CPU Blit: resolution scale above 100% causes a green edge band. Keep resolution scale at 100% and use FSR upscaling."))
        elif self.s.render_path != "cpu_blit" and self.s.aa == "off" and self.s.resolution_scale < 200:
            hints.append(tr("No post AA: use 200% or more resolution, otherwise edges will shimmer."))
        if self.s.aa == "off":
            hints.append(tr("No post AA skips GT6's whole post-process pass, not just MLAA: clouds and sky "
                            "gradients can show colour banding. Use Sharper MLAA for the original look."))
        if self.s.resolution_scale > 100 and self.s.motion_blur.startswith("gameplay"):
            hints.append(tr("Known issue: motion blur can flash green/magenta above 100% resolution."))
        entry = self.current()
        cb, blit = profile.render_flags(self.s, entry.installed if entry else None)
        if blit and not cb:
            hints.append(tr("Force CPU Blit: cars bought or repainted in this mode get a black picture in the "
                            "garage list, and the Paint / Pit Service previews stay black. Races are not affected. "
                            "To fix a car's picture, repaint it once with Render path set to Automatic."))
        if cb and self.s.resolution_scale >= 250:
            hints.append(tr("Heavy: 250-300% with color buffers (needed on 1.22) can drop FPS and make the audio "
                            "crackle. 100-150% is recommended for a steady 60 FPS."))
        if cb and self.s.resolution_scale > 100:
            hints.append(tr("Color buffers are on (1.06+): resolution scaling relies on AlexHaust's res-scale fix "
                            "patches (enabled automatically); the game renders 1440x1080 internally at 100%."))
        if self.s.aspect != "16:9":
            hints.append(tr("Ultrawide: 3D view is widened, HUD and menus stay 16:9."))
        self.gfx_hint.setText("\n".join(hints))
        self.ctl["cas_sharpening"].setEnabled(self.s.upscaler == "fsr")

    AUTO_OPT_BACKUP_KEY = "auto_opt_backup"

    def auto_configure_hardware(self) -> None:
        """Detect CPU, GPU, and RAM, optimize settings for GT6, and provide revert option."""
        # Save snapshot of current settings before optimizing
        self.core.data[self.AUTO_OPT_BACKUP_KEY] = self.s.to_dict()

        cpu_info = profile.detect_cpu_info()
        ram_gb = profile.detect_system_ram_gb()
        adapter = self.s.gpu_adapter
        if not adapter:
            adapters = self.core.gpu_adapters()
            adapter = adapters[0] if adapters else profile.detect_gpu_name()

        recommended, summary = profile.recommend_settings_for_hardware(cpu_info, adapter, ram_gb)
        for k, v in recommended.items():
            setattr(self.s, k, v)

        self.core.save()
        self._load_settings_into_ui()
        self._update_auto_opt_buttons()
        self._fill_patch_list()

        summary_txt = "\n".join(f"• {item}" for item in summary)
        QMessageBox.information(
            self,
            tr("Hardware Auto-Configuration"),
            tr("Optimal settings have been applied based on your detected hardware:\n\n")
            + summary_txt
            + tr("\n\n(You can click 'Restore previous settings' anytime to revert.)")
        )

    def restore_previous_settings(self) -> None:
        """Restore settings backed up before the last auto-configuration."""
        backup = self.core.data.pop(self.AUTO_OPT_BACKUP_KEY, None)
        if not backup or not isinstance(backup, dict):
            QMessageBox.information(self, tr("Restore Settings"), tr("No previous settings backup was found."))
            return
        self.core.settings = self.s = profile.Settings.from_dict(backup)
        self.core.save()
        self._load_settings_into_ui()
        self._update_auto_opt_buttons()
        self._fill_patch_list()
        QMessageBox.information(self, tr("Restore Settings"), tr("Your previous settings have been restored."))

    def _update_auto_opt_buttons(self) -> None:
        if hasattr(self, "restore_opt_btn"):
            has_backup = bool(self.core.data.get(self.AUTO_OPT_BACKUP_KEY))
            self.restore_opt_btn.setEnabled(has_backup)

    def apply_handheld_preset(self) -> None:
        previous = self.core.data.get(self.HANDHELD_RESTORE_KEY)
        if isinstance(previous, dict) and previous:
            for key in profile.HANDHELD_PRESET:
                if key in previous:
                    setattr(self.s, key, previous[key])
            self.core.data.pop(self.HANDHELD_RESTORE_KEY, None)
        else:
            self.core.data[self.HANDHELD_RESTORE_KEY] = {
                key: getattr(self.s, key) for key in profile.HANDHELD_PRESET
            }
            for key, value in profile.HANDHELD_PRESET.items():
                setattr(self.s, key, value)
        self.core.save()
        self._load_settings_into_ui()
        self._update_handheld_preset_button()
        self._fill_patch_list()

    HANDHELD_RESTORE_KEY = "handheld_preset_restore"

    def _update_handheld_preset_button(self) -> None:
        if hasattr(self, "handheld_preset_btn"):
            active = bool(self.core.data.get(self.HANDHELD_RESTORE_KEY))
            self.handheld_preset_btn.setText(
                tr("Restore previous graphics settings") if active else tr("Handheld 800p preset (Steam Deck / 1280x800)"))

    # settings that 'Reset to recommended' (graphics / emulation) must not touch
    RESET_KEEP = ("lan_enabled", "lan_bind_address", "online_enabled", "extra_patches", "gpu_adapter",
                  "controller_mode", "controller_device", "wheel_enabled", "wheel_name", "wheel_mapping", "wheel_reverse_ffb",
                  "console_language", "ui_language", "dev_menu", "fullscreen", "audio_format")

    def reset_profile(self) -> None:
        self.core.data.pop(self.HANDHELD_RESTORE_KEY, None)
        self.core.data.pop(self.AUTO_OPT_BACKUP_KEY, None)
        keep = {k: getattr(self.s, k) for k in self.RESET_KEEP}
        self.core.settings = self.s = profile.Settings.from_dict(keep)
        self.core.save()
        self._load_settings_into_ui()
        self._update_handheld_preset_button()
        self._update_auto_opt_buttons()
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
            self.build_lbl.setText(tr("Emulator component missing - reinstall the launcher.") if not paths.IS_WINDOWS
                                   else tr("Preparing the emulator component..."))
        fw_ok = bool(rp_path) and RPCS3(rp_path).firmware_installed()
        if fw_ok:
            self.fw_lbl.setText(f"{tr('Installed')} (version {RPCS3(rp_path).firmware_version() or '?'})")
            restyle(self.fw_lbl, "ok")
            self.fw_btn.setText(tr("Reinstall firmware"))
            restyle(self.fw_btn, "")
        else:
            self.fw_lbl.setText(tr("Not installed"))
            restyle(self.fw_lbl, "warn")
            self.fw_btn.setText(tr("Install firmware"))
            restyle(self.fw_btn, "accent")
        self.games_lbl.setText(wrap_path("\n".join(f"{g.label}: {g.image.path}" for g in games)) or tr("No game added yet."))
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
            data_ready = mods.game_data_ready(entry.title_id)
            if entry.installed != "01.22":
                lines.append("Needs game version 1.22.")
                self.mod_install_btn.setToolTip("Gran Turismo 6 must be updated to version 1.22 to use mods.")
            elif not data_ready:
                lines.append("Start the game once (update data is unpacked on first boot), then install.")
                self.mod_install_btn.setToolTip("Start the game once on version 1.22 so it can unpack its update data before installing mods.")
            else:
                self.mod_install_btn.setToolTip("")
            self.mod_lbl.setText("\n".join(lines))
            self.mod_install_btn.setEnabled(bool(staged) and entry.installed == "01.22" and data_ready and not stack)
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
        self._update_gpu_warning(self.s.gpu_adapter)

        # left status
        if not entry:
            st = tr("Add your Gran Turismo 6 disc image in Setup.")
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
        self.play_btn.setText(tr("RUNNING") if self.proc else tr("PLAY"))
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
        if not mods.game_data_ready(entry.title_id):
            QMessageBox.warning(self, "Game not ready",
                                "Start the game once on version 1.22 and wait for the main menu.\n\n"
                                "Gran Turismo 6 unpacks its update data on the first boot (~20 mins). "
                                "Mods can only be installed after this step completes.")
            return

        def work(job):
            n = 0
            for m in mods.KNOWN_MODS:  # dependency order
                if mods.staged(m.id) and m.id not in mods.installed_stack(entry.title_id):
                    n += mods.install(entry.title_id, m.id, job.progress)
            return n
        self._run("Install mods", work, lambda n: self._append_log(f"installed {n} mod files"))

    def uninstall_mods(self, entry=None) -> None:
        entry = entry or self.current()
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
            QMessageBox.information(self, "Config", "Written. Enabled patches:\n" + "\n".join(names))

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
        if not self._confirm_hardware():
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
            self._proc_log_start_line = len(self.log_view.toPlainText().splitlines())
            self.proc = self.core.launch(entry)
            self._proc_entry = entry
            self._proc_started = __import__("time").time()
            self._append_log(f"started {entry.title_id} (pid {self.proc.pid})")
        except Exception as e:  # noqa: BLE001
            self._append_log(traceback.format_exc())
            QMessageBox.warning(self, "Start", str(e))
        self.refresh()

    def _confirm_hardware(self) -> bool:
        if self._hardware_warning_shown:
            return True
        warnings = self.core.hardware_advisory()
        if not warnings:
            return True
        self._hardware_warning_shown = True
        output = self.s.output_resolution.split("x")
        if len(output) == 2 and all(part.isdigit() for part in output):
            width = int(int(output[0]) * self.s.resolution_scale / 100)
            height = int(int(output[1]) * self.s.resolution_scale / 100)
            render_target = tr("Current internal target: approximately {w}x{h} ({scale}%).").format(
                w=width, h=height, scale=self.s.resolution_scale)
        else:
            render_target = tr("Current resolution scale: {scale}%.").format(scale=self.s.resolution_scale)
        adapters = self.core.gpu_adapters()
        gpu = ", ".join(adapters) if adapters else tr("not identified in an RPCS3 log yet")
        box = QMessageBox(self)
        box.setWindowTitle(tr("Hardware may struggle with GT6"))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(tr("This PC may struggle to run Gran Turismo 6 smoothly."))
        box.setInformativeText("\n".join(warnings) + "\n" + tr("Detected Vulkan GPU: {gpu}").format(gpu=gpu)
                               + f"\n{render_target}\n\n"
                               + tr("Lowering the output resolution or internal resolution scale may help. "
                                    "This is an advisory only; you can continue if you want to try."))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.button(QMessageBox.StandardButton.Yes).setText(tr("Continue"))
        box.button(QMessageBox.StandardButton.Cancel).setText(tr("Cancel"))
        return box.exec() == QMessageBox.StandardButton.Yes

    def _check_external_rpcs3_launch(self) -> None:
        try:
            marker = diagnostics.direct_rpcs3_launch_marker()
        except OSError:
            return
        if marker and marker != self._last_direct_rpc_origin:
            self._last_direct_rpc_origin = marker
            diagnostics.record_direct_rpcs3_launch(marker)
            self._append_log(f"[diagnostic] {marker}")

    def _poll_proc(self) -> None:
        self._check_external_rpcs3_launch()
        if self.proc and self.proc.poll() is not None:
            proc = self.proc
            self._append_log(f"game exited (code {proc.returncode})")
            lines = self.log_view.toPlainText().splitlines()
            start = getattr(self, "_proc_log_start_line", 0)
            try:
                if not diagnostics.remember_last_session("\n".join(lines[start:])):
                    self._append_log("[session log] RPCS3 log could not be snapshotted")
            except OSError as e:
                self._append_log(f"[session log] snapshot failed: {e}")
            if proc.returncode != 0:
                try:
                    report = diagnostics.collect_crash(
                        self._proc_entry, proc, self._proc_started, self.core.rpcs3_path() or "(unknown)")
                    self._append_log(f"[abnormal exit] diagnostic report saved: {report}")
                except Exception as e:  # noqa: BLE001
                    self._append_log(f"[diagnostics failed] could not save crash report: {e}")
            ran_for = __import__("time").time() - getattr(self, "_proc_started", 0)
            if ran_for > 180:
                self.core.mark_compiled(self._proc_entry)
            try:
                if self.core.sync_ingame_color_grading(self._proc_entry.title_id):
                    self._append_log("color grading: picked up the values saved in the in-game home menu")
                    self._load_settings_into_ui()
            except Exception:  # noqa: BLE001
                self._append_log(traceback.format_exc())
            self.proc = None
            self.refresh()
            entry = self._proc_entry
            if proc.returncode == 0 and entry and mods.installed_stack(entry.title_id):
                # Time the game itself ran, not RPCS3's start-up/compile time (#53: 74 s total, 4 s of game)
                game_ran = diagnostics.game_run_seconds()
                quick = game_ran if game_ran is not None and game_ran < QUICK_EXIT_SECONDS else (
                    ran_for if ran_for < QUICK_EXIT_SECONDS else None)
                if quick is not None:
                    QTimer.singleShot(0, lambda: self._offer_mod_uninstall(entry, quick))

    def _offer_mod_uninstall(self, entry, ran_for: float) -> None:
        """The game closed by itself within seconds while mods are installed (issue #49): on some PCs the
        Spec II / Career mod files make GT6 quit right after boot. Offer the one-click restore."""
        self._append_log(f"[mods] game closed after {ran_for:.0f} s with mods installed - offering uninstall")
        box = QMessageBox(self)
        box.setWindowTitle(tr("Game closed right after starting"))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(tr("Gran Turismo 6 closed by itself right after starting."))
        box.setInformativeText(tr("Mods are installed, and on some PCs the mods make the game close at start-up.\n\n"
                               "Uninstall all mods now? The original game files are restored exactly and your "
                               "save data is not touched. You can install the mods again later from the Mods tab."))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText(tr("Uninstall mods"))
        box.button(QMessageBox.StandardButton.No).setText(tr("Keep mods"))
        if box.exec() == QMessageBox.StandardButton.Yes:
            self.uninstall_mods(entry)

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

    def _update_egg_btn_pos(self) -> None:
        if hasattr(self, "egg_btn") and hasattr(self, "tabs"):
            bar = self.tabs.tabBar()
            last_idx = -1
            for i in range(bar.count() - 1, -1, -1):
                if self.tabs.isTabVisible(i):
                    last_idx = i
                    break
            if last_idx >= 0:
                rect = bar.tabRect(last_idx)
                bar_pos = bar.pos()
                self.egg_btn.move(bar_pos.x() + rect.right() + 2, bar_pos.y() + rect.top())
                self.egg_btn.show()
                self.egg_btn.raise_()

    def _play_easter_egg(self) -> None:
        if getattr(self, "_egg_overlay", None) is not None:
            return
        webp = paths.resource("easteregg/dingdong.webp")
        wav = paths.resource("easteregg/dingdong.wav")
        if not os.path.exists(webp) or not os.path.exists(wav):
            return

        def done():
            self._egg_overlay = None

        self._egg_overlay = EasterEggOverlay(self, webp, wav, on_finished=done)


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
        ("up", "Press D-pad UP.", "any", True),
        ("down", "Press D-pad DOWN.", "any", True),
        ("left", "Press D-pad LEFT.", "any", True),
        ("right", "Press D-pad RIGHT.", "any", True),
        ("l2", "Press the button you want as L2 (look left / back).", "any", True),
        ("r2", "Press the button you want as R2 (look right).", "any", True),
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
        self.setWindowTitle(tr("Racing wheel set-up"))
        self.setMinimumWidth(560)
        self.mapping: dict = {}
        self.wheel_name = ""
        self.used: set = set()
        v = QVBoxLayout(self)
        self.devices_lbl = label("", 9, name="muted")
        v.addWidget(self.devices_lbl)

        # Calibration controls container
        self.calib_container = QWidget()
        calib_v = QVBoxLayout(self.calib_container)
        calib_v.setContentsMargins(0, 0, 0, 0)

        target_row = QHBoxLayout()
        target_row.addWidget(label(tr("Capture controls from:"), 9, name="muted"))
        self.device_box = QComboBox()
        self.device_box.setToolTip("Choose the wheel or another input device. Select a different device for separate USB pedals or shifters.")
        target_row.addWidget(self.device_box, 1)
        self.refresh_devices_btn = QPushButton(tr("Refresh"))
        self.refresh_devices_btn.clicked.connect(self._rescan_devices)
        target_row.addWidget(self.refresh_devices_btn)
        calib_v.addLayout(target_row)
        self.device_box.currentIndexChanged.connect(self._capture_device_changed)
        self._refresh_capture_devices()

        self.step_lbl = label("", 9, name="muted")
        calib_v.addWidget(self.step_lbl)
        self.instr = label("", 13, True)
        self.instr.setMinimumHeight(70)
        calib_v.addWidget(self.instr)

        self.axis_meter = QWidget()
        axis_row = QHBoxLayout(self.axis_meter)
        axis_row.setContentsMargins(0, 0, 0, 4)
        axis_row.addWidget(label(tr("Input level:"), 9, name="muted"))
        self.axis_bar = QProgressBar()
        self.axis_bar.setRange(0, 100)
        self.axis_bar.setValue(0)
        self.axis_bar.setTextVisible(False)
        self.axis_bar.setFixedHeight(14)
        axis_row.addWidget(self.axis_bar, 1)
        self.axis_pct_lbl = label("0%", 10, True)
        self.axis_pct_lbl.setMinimumWidth(44)
        self.axis_pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        axis_row.addWidget(self.axis_pct_lbl)
        calib_v.addWidget(self.axis_meter)

        self.status = label("", 10, name="ok")
        calib_v.addWidget(self.status)
        v.addWidget(self.calib_container)

        # Review & test container
        self.review_container = QWidget()
        self.review_layout = QVBoxLayout(self.review_container)
        self.review_layout.setContentsMargins(0, 0, 0, 0)
        self.review_bars: dict[str, QProgressBar] = {}
        self.review_container.setVisible(False)
        v.addWidget(self.review_container)

        h = QHBoxLayout()
        self.back_btn = QPushButton(tr("Back"))
        self.back_btn.clicked.connect(self._back)
        h.addWidget(self.back_btn)
        h.addStretch(1)

        self.finish_btn = QPushButton(tr("Save & Finish"))
        self.finish_btn.setObjectName("accent")
        self.finish_btn.clicked.connect(self._finish)
        self.finish_btn.setVisible(False)
        h.addWidget(self.finish_btn)

        self.skip_btn = QPushButton(tr("Skip"))
        self.skip_btn.clicked.connect(self._skip)
        h.addWidget(self.skip_btn)
        cancel = QPushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        h.addWidget(cancel)
        v.addLayout(h)

        self.i = 0
        self.phase = "arm"
        self.hit_control = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self._start_step()
        self.timer.start(25)

    def _start_step(self) -> None:
        self.hit_control = None
        names = [f"{d['name']} ({d['vendor']:04X}:{d['product']:04X}, {d['axes']} axes)"
                 + ("  (wheel)" if d["is_wheel"] else "") for d in self.js.devices]
        self.devices_lbl.setText("Detected: " + (", ".join(names) or "no controllers - connect your wheel"))
        if self.i >= len(self.STEPS):
            self._show_review()
            return
        self.calib_container.setVisible(True)
        self.review_container.setVisible(False)
        self.finish_btn.setVisible(False)
        self.skip_btn.setVisible(True)
        key, text, kind, optional = self.STEPS[self.i]
        # Restarting a step (Refresh, device change) must forget what this step already captured,
        # otherwise a wrong capture stays in self.used and later steps ignore that axis (issue #41).
        if self.mapping.pop(key, None) is not None:
            self._rebuild_used()
        self.step_lbl.setText(f"Step {self.i + 1} of {len(self.STEPS)}")
        self.instr.setText(text)
        self.axis_meter.setVisible(kind == "axis")
        self.axis_bar.setValue(0)
        self.axis_pct_lbl.setText("0%")
        self.status.setText("")
        self.skip_btn.setEnabled(optional)
        self.back_btn.setEnabled(self.i > 0)
        self.phase = "settle"
        now = __import__("time").time()
        self.settle_until = now + 0.3
        self.settle_deadline = now + 2.0
        self.settle_prev = None
        self.base = None

    def _show_review(self) -> None:
        self.phase = "review"
        self.calib_container.setVisible(False)
        self.skip_btn.setVisible(False)
        self.finish_btn.setVisible(True)
        self.back_btn.setEnabled(True)

        while self.review_layout.count():
            item = self.review_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.review_bars.clear()
        self.review_layout.addWidget(label(tr("Controls Review & Test"), 13, True))
        self.review_layout.addWidget(label(
            tr("Test your steering and pedals below. If any pedal is pressed when released, check 'Invert'."),
            9, name="muted"
        ))

        grid = QGridLayout()
        row = 0
        axes_to_show = [("steering", "Steering"), ("throttle", "Throttle"), ("brake", "Brake"), ("clutch", "Clutch")]
        for key, title in axes_to_show:
            m = self.mapping.get(key)
            if not m or m.get("type") != "axis":
                continue
            grid.addWidget(label(tr(title), 10, True), row, 0)
            bar = QProgressBar()
            if key == "steering":
                bar.setRange(-100, 100)
                bar.setValue(0)
                bar.setFormat("%v%")
            else:
                bar.setRange(0, 100)
                bar.setValue(0)
                bar.setFormat("%v%")
            grid.addWidget(bar, row, 1)
            self.review_bars[key] = bar

            inv_chk = QCheckBox(tr("Invert"))
            inv_chk.setChecked(bool(m.get("reverse", False)))
            inv_chk.toggled.connect(lambda checked, k=key: self._set_mapping_reverse(k, checked))
            grid.addWidget(inv_chk, row, 2)
            row += 1

        self.review_layout.addLayout(grid)
        self.review_btn_lbl = label(tr("Buttons: press any mapped button to test"), 9, name="muted")
        self.review_layout.addWidget(self.review_btn_lbl)
        self.review_container.setVisible(True)

    def _set_mapping_reverse(self, key: str, rev: bool) -> None:
        if key in self.mapping:
            self.mapping[key]["reverse"] = rev

    def _update_review(self, now: list[dict]) -> None:
        for k, bar in self.review_bars.items():
            m = self.mapping.get(k)
            if not m or m.get("type") != "axis":
                continue
            target_di = None
            for di, d in enumerate(self.js.devices):
                if d["type_id"] == m["device_type_id"]:
                    target_di = di
                    break
            if target_di is None or target_di >= len(now):
                continue
            axes = now[target_di].get("axes", [])
            axis_id = m["id"]
            if axis_id >= len(axes):
                continue
            raw = axes[axis_id]
            rev = m.get("reverse", False)
            if rev:
                raw = -raw
            if k == "steering":
                pct = int(max(-100, min(100, (raw / 32767.0) * 100)))
                bar.setValue(pct)
            else:
                pct = int(max(0, min(100, (0x7FFF - raw) / 65535.0 * 100)))
                bar.setValue(pct)

        pressed_names = []
        for k, m in self.mapping.items():
            if m.get("type") != "button":
                continue
            target_di = None
            for di, d in enumerate(self.js.devices):
                if d["type_id"] == m["device_type_id"]:
                    target_di = di
                    break
            if target_di is None or target_di >= len(now):
                continue
            buttons = now[target_di].get("buttons", [])
            btn_id = m["id"]
            if btn_id < len(buttons) and buttons[btn_id]:
                pressed_names.append(k.upper())
        if pressed_names:
            self.review_btn_lbl.setText(f"{tr('Pressed')}: {', '.join(pressed_names)}")

    def _refresh_capture_devices(self) -> None:
        selected = self.device_box.currentData() if hasattr(self, "device_box") else None
        self.device_box.blockSignals(True)
        self.device_box.clear()
        self.device_box.addItem("Select a device...", "__select__")
        ids = set()
        for d in self.js.devices:
            tid = d["type_id"]
            if tid in ids:
                continue  # RPCS3 also treats devices with the same type ID as one device group.
            ids.add(tid)
            self.device_box.addItem(f"{d['name']} ({d['vendor']:04X}:{d['product']:04X})", tid)
        self.device_box.addItem("Any detected device (advanced)", None)
        preferred = selected if selected in ids else None
        if preferred is None:
            wheels = [d["type_id"] for d in self.js.devices if d["is_wheel"]]
            if len(set(wheels)) == 1:
                preferred = wheels[0]
            elif len(ids) == 1:
                preferred = next(iter(ids))
        if preferred is not None:
            index = self.device_box.findData(preferred)
            if index >= 0:
                self.device_box.setCurrentIndex(index)
        self.device_box.blockSignals(False)

    def _capture_device_changed(self, _index: int) -> None:
        if hasattr(self, "timer") and self.timer.isActive() and self.i < len(self.STEPS):
            self._start_step()

    def _rescan_devices(self) -> None:
        self.js.refresh()
        self._refresh_capture_devices()
        self._start_step()

    def _poll(self) -> None:
        import time
        if not self.js.devices:
            self._rescan = getattr(self, "_rescan", 0) + 1
            if self._rescan % 40 == 1:  # about once a second (timer runs every 25 ms)
                self.js.refresh()
                self._refresh_capture_devices()
            if not self.js.devices:
                self.devices_lbl.setText("Detected: no controllers - connect your wheel")
                return
            self._start_step()  # device appeared: show it and take a fresh baseline
            return
        now = self.js.state()
        if self.phase == "review":
            self._update_review(now)
            return
        if self.phase == "settle":  # wait until the previous control is released, then take a baseline
            # Only take the baseline once every axis has held still for 0.3 s (max 2 s). Some wheels
            # (G923 on Windows) report pedals as 0 until their first input report arrives; a baseline
            # taken before that makes the pedal's jump to its rest value look like movement (#41).
            t = time.time()
            if self.settle_prev is not None and self._axes_moved(self.settle_prev, now):
                self.settle_until = t + 0.3
            self.settle_prev = now
            if t >= self.settle_until or t >= self.settle_deadline:
                self.base, self.phase = now, "wait"
            return
        if self.phase == "release":
            if self.hit_control is not None:
                if self.hit_control.get("type") == "axis":
                    self._update_axis_meter_release(self.hit_control, now)
                if self._is_released(self.hit_control, now):
                    self.i += 1
                    self._start_step()
            return
        key, _text, kind, _opt = self.STEPS[self.i]
        self._adopt_late_axes(now)
        exclude = set(self.used)
        if key in ("throttle", "brake"):
            other_pedal = self.mapping.get("brake" if key == "throttle" else "throttle")
            if other_pedal and other_pedal["type"] == "axis":
                # Combined-pedal wheels expose accelerator and brake on opposite ends of one axis.
                exclude.discard((other_pedal["device_type_id"], "axis", other_pedal["id"]))
        if key in ("left", "right"):
            other_dpad = self.mapping.get("right" if key == "left" else "left")
            if other_dpad and other_dpad["type"] == "axis":
                exclude.discard((other_dpad["device_type_id"], "axis", other_dpad["id"]))
        if key in ("up", "down"):
            other_dpad = self.mapping.get("down" if key == "up" else "up")
            if other_dpad and other_dpad["type"] == "axis":
                exclude.discard((other_dpad["device_type_id"], "axis", other_dpad["id"]))
        selected_device = self.device_box.currentData()
        if selected_device == "__select__":
            self.status.setText("Choose the wheel or input device above before calibrating this control.")
            return
        allowed = {int(selected_device)} if selected_device is not None else None
        if kind == "axis":
            self._update_axis_meter_wait(now, exclude, allowed)
        hit = self.gp.detect_change(self.base, now, self.js.devices, kind, exclude, allowed)
        if not hit and allowed is not None:
            # Multi-device setups (separate USB shifter / pedals): if an input was made on
            # another connected controller, auto-switch the device box to it.
            other_hit = self.gp.detect_change(self.base, now, self.js.devices, kind, exclude, None)
            if other_hit:
                idx = self.device_box.findData(other_hit["device_type_id"])
                if idx >= 0:
                    self.device_box.blockSignals(True)
                    self.device_box.setCurrentIndex(idx)
                    self.device_box.blockSignals(False)
                    hit = other_hit
        if not hit:
            return
        self._fix_late_rest(hit, key)
        self.hit_device_type_id = hit["device_type_id"]
        self.hit_control = hit
        m = {"device_type_id": hit["device_type_id"], "type": hit["type"], "id": hit["id"], "hat": hit["hat"],
             "reverse": False}
        if hit["type"] == "axis":
            self.axis_bar.setValue(100)
            self.axis_pct_lbl.setText("100%")
            if key == "steering":
                # Steering: turning right must increase axis value
                m["reverse"] = hit["moved"] < hit["rest"]
            else:
                # Pedals (throttle, brake, clutch): in RPCS3's Logitech G27 emulation
                # (LogitechG27.cpp), 0x00 is Pressed and 0xFF is Released.
                # Released pedal must read as axis maximum (+32767), and pressed pedal
                # must read as axis minimum (-32768).
                # If pressing the pedal increases the axis value, it must be inverted (reverse = True).
                # If pressing the pedal decreases the axis value (e.g. Thrustmaster T150/T300 resting
                # at +32767 and moving to -32768), reverse must be False.
                m["reverse"] = hit["moved"] > hit["rest"]
            self.used.add((hit["device_type_id"], "axis", hit["id"]))
        elif hit["type"] == "hat":
            self.used.add((hit["device_type_id"], "hat", hit["id"], hit["hat"]))
        else:
            self.used.add((hit["device_type_id"], "button", hit["id"]))
        self.mapping[key] = m
        if key == "steering":
            dev = next(d for d in self.js.devices if d["type_id"] == hit["device_type_id"])
            self.wheel_name = dev["name"]
            if self.device_box.currentData() is None:
                idx = self.device_box.findData(hit["device_type_id"])
                if idx >= 0:
                    self.device_box.blockSignals(True)
                    self.device_box.setCurrentIndex(idx)
                    self.device_box.blockSignals(False)
        what = f"{hit['type']} {hit['id']}" + (f" {hit['hat']}" if hit["hat"] else "")
        self.status.setText(f"OK - {what}. Release it...")
        self.phase = "release"

    def _update_axis_meter_wait(self, now: list[dict], exclude: set, allowed: Optional[set[int]]) -> None:
        """Show live axis movement as 0-100% of the capture threshold during axis calibration."""
        threshold = 0x7FFF * 0.35
        max_delta = 0.0
        for di, (b, n) in enumerate(zip(self.base or [], now)):
            tid = self.js.devices[di]["type_id"]
            if allowed is not None and tid not in allowed:
                continue
            for i, (bv, nv) in enumerate(zip(b["axes"], n["axes"])):
                if (tid, "axis", i) in exclude:
                    continue
                d = abs(nv - bv)
                if d > max_delta:
                    max_delta = d
        if max_delta < threshold * 0.05 and allowed is not None:
            for di, (b, n) in enumerate(zip(self.base or [], now)):
                tid = self.js.devices[di]["type_id"]
                for i, (bv, nv) in enumerate(zip(b["axes"], n["axes"])):
                    if (tid, "axis", i) in exclude:
                        continue
                    d = abs(nv - bv)
                    if d > max_delta:
                        max_delta = d
        pct = int(min(100, max(0, (max_delta / threshold) * 100)))
        self.axis_bar.setValue(pct)
        self.axis_pct_lbl.setText(f"{pct}%")

    def _update_axis_meter_release(self, hit: dict, now: list[dict]) -> None:
        """Show the captured axis returning to 0% as the user releases/centers it."""
        for di, d in enumerate(self.js.devices):
            if d["type_id"] == hit["device_type_id"] and di < len(now):
                axes = now[di].get("axes", [])
                idx = hit["id"]
                if idx < len(axes):
                    rest = hit.get("rest", 0)
                    moved = hit.get("moved", 0)
                    denom = max(abs(moved - rest), 0x7FFF * 0.35)
                    pct = int(min(100, max(0, (abs(axes[idx] - rest) / denom) * 100)))
                    self.axis_bar.setValue(pct)
                    self.axis_pct_lbl.setText(f"{pct}%")
                break

    def _is_released(self, hit: dict, now: list[dict]) -> bool:
        """Check if the specific control that was just calibrated has been released/centered."""
        target_di = None
        for di, d in enumerate(self.js.devices):
            if d["type_id"] == hit["device_type_id"]:
                target_di = di
                break
        if target_di is None or target_di >= len(now):
            return True
        dev_now = now[target_di]
        kind = hit["type"]
        idx = hit["id"]
        if kind == "button":
            buttons = dev_now.get("buttons", [])
            return idx >= len(buttons) or not buttons[idx]
        elif kind == "hat":
            hats = dev_now.get("hats", [])
            if idx < len(hats):
                hat_val = hats[idx]
                bit = next((b for b, name in self.gp.HAT_BITS.items() if name == hit.get("hat")), 0)
                return (hat_val & bit) == 0 if bit else hat_val == 0
            return True
        elif kind == "axis":
            axes = dev_now.get("axes", [])
            if idx < len(axes):
                current_val = axes[idx]
                rest_val = hit.get("rest", 0)
                moved_val = hit.get("moved", 0)
                travel = abs(moved_val - rest_val)
                dist = abs(current_val - rest_val)
                if travel > 0:
                    return dist <= travel * 0.35 or dist <= 0x7FFF * 0.2
                return dist <= 0x7FFF * 0.2
            return True
        return True

    def _skip(self) -> None:
        key = self.STEPS[self.i][0]
        self.mapping.pop(key, None)
        if key == "shifter_1":  # no H-shifter: skip all gears
            self.i = next(j for j, s in enumerate(self.STEPS) if s[0] == "shifter_r") + 1
        else:
            self.i += 1
        self._start_step()

    def _back(self) -> None:
        if self.phase == "review":
            self.review_container.setVisible(False)
            self.calib_container.setVisible(True)
            self.finish_btn.setVisible(False)
            self.skip_btn.setVisible(True)
            self.i = len(self.STEPS) - 1
            old = self.mapping.pop(self.STEPS[self.i][0], None)
            if old:
                self._rebuild_used()
            self._start_step()
            return
        if self.i > 0:
            self.i -= 1
            old = self.mapping.pop(self.STEPS[self.i][0], None)
            if old:
                self._rebuild_used()
            self._start_step()

    def _adopt_late_axes(self, now: list[dict]) -> None:
        """Issue #41 (G923 on Windows): SDL reads 0 for every axis until the device sends its first
        report, which only happens when something moves. Turning the wheel then makes the pedals
        jump from 0 to their rest value (an end of the range), which looked like a full pedal
        movement and was captured as steering. When an axis reports for the first time at an end
        of its range, take that value as its baseline instead of treating the jump as movement.
        An axis that first reports somewhere in between is the one being moved; its rest value is
        fixed up when it is captured (_fix_late_rest)."""
        for b, n in zip(self.base or [], now):
            was, isnow = b.get("reported"), n.get("reported")
            if was is None or isnow is None:
                continue
            for i, (before, after) in enumerate(zip(was, isnow)):
                if not before and after and abs(n["axes"][i]) >= 0x7FFF * 0.9:
                    b["axes"][i] = n["axes"][i]
                    was[i] = True

    def _fix_late_rest(self, hit: dict, key: str) -> None:
        """A pedal whose device had not reported at baseline reads 0 there, not its real rest
        value. Pedals rest at one end of the range, the end opposite to where they were pressed."""
        if hit.get("type") != "axis" or key not in ("throttle", "brake", "clutch"):
            return
        di = next((i for i, d in enumerate(self.js.devices) if d["type_id"] == hit["device_type_id"]), None)
        if di is None or di >= len(self.base or []):
            return
        reported = self.base[di].get("reported")
        if reported is None or hit["id"] >= len(reported) or reported[hit["id"]]:
            return
        hit["rest"] = -0x8000 if hit["moved"] > 0 else 0x7FFF

    @staticmethod
    def _axes_moved(prev: list[dict], now: list[dict]) -> bool:
        """True if any axis changed by more than 5 % of its range between two snapshots."""
        if len(prev) != len(now):
            return True
        for p, n in zip(prev, now):
            for pv, nv in zip(p.get("axes", []), n.get("axes", [])):
                if abs(nv - pv) > 0x7FFF * 0.05:
                    return True
        return False

    def _rebuild_used(self) -> None:
        self.used = set()
        for mapped in self.mapping.values():
            if mapped.get("type") == "hat":
                self.used.add((mapped["device_type_id"], "hat", mapped["id"], mapped.get("hat")))
            else:
                self.used.add((mapped["device_type_id"], mapped["type"], mapped["id"]))

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
    win._update_egg_btn_pos()


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
