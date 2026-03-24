import sys
import os
from datetime import datetime

import PyQt5
_qt_plugin_path = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", _qt_plugin_path)

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QButtonGroup, QRadioButton, QGroupBox, QFrame, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QLinearGradient, QColor, QBrush


# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────
FRAME_COLORS = {
    "흰색":       (255, 255, 255),
    "검정":       (30,  30,  30),
    "브라운":     (73, 53, 40),
    "스카이블루":  (202, 230, 249),
    "베이비핑크":  (243, 213, 223),
}

PHOTO_W, PHOTO_H = 400, 300
PADDING, BORDER  = 20, 30
LOGO_AREA_H      = 130  # 로고 영역 높이 (로고 + 아래 여백 포함)

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
LOGO_BLACK = os.path.join(IMG_DIR, "cartoonbooth_logo_black.png")
LOGO_WHITE = os.path.join(IMG_DIR, "cartoonbooth_logo_white.png")

# 밝은 배경 → 검정 로고 / 어두운 배경 → 흰색 로고
_DARK_BG_COLORS = {"검정", "브라운"}

def _get_logo(color_name: str) -> Image.Image:
    path = LOGO_WHITE if color_name in _DARK_BG_COLORS else LOGO_BLACK
    return Image.open(path).convert("RGBA")

STYLE = """
QWidget { background:#f5f0e8; color:#3b2a1a;
          font-family:'Malgun Gothic',sans-serif; font-size:14px; }
QGroupBox { border:1px solid #e8c9a0; border-radius:8px;
            margin-top:14px; padding:10px; font-weight:bold;
            background:#fdf7ee; }
QGroupBox::title { subcontrol-origin:margin; left:10px; color:#d94f1e; }
QPushButton { background:#fdebd8; border:1px solid #e8c9a0;
              border-radius:8px; padding:10px 22px; color:#3b2a1a; }
QPushButton:hover  { background:#fad9b8; }
QPushButton:pressed { background:#f5c49a; }
QPushButton#primary { background:#e85d1a; color:#fff7f0;
                      font-weight:bold; border:none; }
QPushButton#primary:hover { background:#d94f10; }
QPushButton#danger  { background:#c0392b; color:#fff7f0;
                      font-weight:bold; border:none; }
QRadioButton { spacing:8px; font-size:15px; color:#3b2a1a; }
QRadioButton::indicator { width:18px; height:18px; }
QLabel#step { font-size:13px; color:#b07040; }
QLabel#title { font-size:22px; font-weight:bold; color:#d94f1e; }
QScrollArea { background:#f5f0e8; border:1px solid #e8c9a0; border-radius:8px; }
"""


# ──────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────
def apply_cartoon(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    small = cv2.resize(bgr, (w * 3 // 4, h * 3 // 4))  # 3/4 해상도로 블러 감소

    # ── 엣지 (선) ─────────────────────────────────────────────
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    edges = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY, blockSize=15, C=8
    )
    edges = cv2.medianBlur(edges, 3)

    # ── 색상 평탄화 (sigma 낮춰 블러 감소) ────────────────────
    color = cv2.bilateralFilter(small, 5, 25, 25)

    # ── 채도 부스트 (만화 그림체) ─────────────────────────────
    hsv = cv2.cvtColor(color, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.5, 0, 255)  # 채도 1.5배
    color = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    cartoon_small = cv2.bitwise_and(color, color, mask=edges)
    return cv2.resize(cartoon_small, (w, h))


def draw_countdown(bgr: np.ndarray, text: str) -> np.ndarray:
    """카운트다운 숫자를 프레임 위에 직접 오버레이"""
    out = bgr.copy()
    h, w = out.shape[:2]
    font       = cv2.FONT_HERSHEY_PLAIN
    font_scale = 2.5
    thickness  = 3
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x = (w - tw) // 2
    y = (h + th) // 2
    cv2.putText(out, text, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return out


def bgr_to_pixmap(bgr: np.ndarray, max_w=640, max_h=480) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qi = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qi).scaled(
        max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )


def build_frame(photos: list, layout: str, color_name: str) -> Image.Image:
    bg = FRAME_COLORS[color_name]
    if layout == "단일":
        cols, rows = 1, 1
    elif layout == "세로4컷":
        cols, rows = 1, 4
    else:
        cols, rows = 3, 1
    cw = BORDER * 2 + cols * PHOTO_W + (cols - 1) * PADDING
    ch = BORDER * 2 + rows * PHOTO_H + (rows - 1) * PADDING + LOGO_AREA_H
    canvas = Image.new("RGB", (cw, ch), bg)
    for i, img in enumerate(photos[:cols * rows]):
        img = img.resize((PHOTO_W, PHOTO_H), Image.LANCZOS)
        if cols == 1:
            x, y = BORDER, BORDER + i * (PHOTO_H + PADDING)
        else:
            x, y = BORDER + i * (PHOTO_W + PADDING), BORDER
        canvas.paste(img, (x, y))

    # 로고 삽입
    logo = _get_logo(color_name)
    max_logo_w = cw - BORDER * 4
    max_logo_h = LOGO_AREA_H - 60
    logo.thumbnail((max_logo_w, max_logo_h), Image.LANCZOS)
    lx = (cw - logo.width) // 2
    ly = ch - LOGO_AREA_H + (LOGO_AREA_H - logo.height) // 2 - 15
    canvas.paste(logo, (lx, ly), mask=logo)

    return canvas


# ──────────────────────────────────────────────────────────────
# 카메라 스레드
# ──────────────────────────────────────────────────────────────
class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self._running = False

    def run(self):
        cap = cv2.VideoCapture(0)
        self._running = True
        while self._running:
            ret, frame = cap.read()
            if ret:
                self.frame_ready.emit(frame)
        cap.release()

    def stop(self):
        self._running = False
        self.wait()


# ══════════════════════════════════════════════════════════════
# Step 1 – 프레임 레이아웃 선택
# ══════════════════════════════════════════════════════════════
LAYOUTS = [
    ("세로4컷", "frame_horizontal.png"),
    ("가로3컷", "frame_vertical.png"),
    ("단일",    "frame_single.png"),
]

CARD_BASE = """
    QFrame {{
        background: {bg};
        border: 3px solid {border};
        border-radius: 14px;
    }}
    QLabel#card_title {{
        font-size: 14px;
        font-weight: bold;
        color: {fg};
        background: transparent;
        border: none;
    }}
"""
CARD_NORMAL   = {"bg": "#fdebd8", "border": "#e8c9a0", "fg": "#3b2a1a"}
CARD_SELECTED = {"bg": "#fde0c8", "border": "#e85d1a", "fg": "#d94f1e"}


class FilmBanner(QWidget):
    """그라데이션 + 필름 스트립 구멍 배너"""
    def __init__(self, logo_path: str):
        super().__init__()
        self.setFixedHeight(90)
        self._logo = QPixmap(logo_path)
        if not self._logo.isNull():
            self._logo = self._logo.scaled(240, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # 세로 그라데이션: #FF9562(위) → #e85d1a(아래)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#FF9562"))
        grad.setColorAt(1.0, QColor("#e85d1a"))
        p.fillRect(0, 0, w, h, QBrush(grad))

        # 로고 중앙
        if not self._logo.isNull():
            lx = (w - self._logo.width()) // 2
            ly = (h - self._logo.height()) // 2
            p.drawPixmap(lx, ly, self._logo)

        p.end()


class LayoutCard(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, idx: int, name: str, img_path: str):
        super().__init__()
        self.idx = idx
        self.setFixedSize(210, 270)
        self.setCursor(Qt.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(8)

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setStyleSheet("border:none; background:transparent;")
        pix = QPixmap(img_path)
        if not pix.isNull():
            img_lbl.setPixmap(pix.scaled(170, 210, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(img_lbl, stretch=1)

        title_lbl = QLabel(name)
        title_lbl.setObjectName("card_title")
        title_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(title_lbl)

    def mousePressEvent(self, _):
        self.clicked.emit(self.idx)


class Step1Widget(QWidget):
    next_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.selected = 0
        self.cards: list[LayoutCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 30)
        root.setSpacing(20)

        step_lbl = QLabel("STEP 1 / 3")
        step_lbl.setObjectName("step")
        root.addWidget(step_lbl, alignment=Qt.AlignCenter)

        # 그라데이션 + 필름 스트립 배너
        banner = FilmBanner(LOGO_WHITE)
        root.addWidget(banner)

        title = QLabel("프레임 레이아웃 선택")
        title.setObjectName("title")
        root.addWidget(title, alignment=Qt.AlignCenter)

        card_row = QHBoxLayout()
        card_row.setSpacing(24)
        for i, (name, img_file) in enumerate(LAYOUTS):
            img_path = os.path.join(IMG_DIR, img_file)
            card = LayoutCard(i, name, img_path)
            card.clicked.connect(self._select)
            self.cards.append(card)
            card_row.addWidget(card)
        root.addLayout(card_row, stretch=1)

        self.btn_next = QPushButton("다음  →")
        self.btn_next.setObjectName("primary")
        self.btn_next.setFixedSize(160, 48)
        self.btn_next.clicked.connect(self._next)
        root.addWidget(self.btn_next, alignment=Qt.AlignCenter)

        self._select(0)

    def _select(self, idx: int):
        self.selected = idx
        for i, card in enumerate(self.cards):
            c = CARD_SELECTED if i == idx else CARD_NORMAL
            card.setStyleSheet(CARD_BASE.format(**c))

    def _next(self):
        self.next_signal.emit(LAYOUTS[self.selected][0])


# ══════════════════════════════════════════════════════════════
# Step 2 – 촬영
# ══════════════════════════════════════════════════════════════
class Step2Widget(QWidget):
    done_signal = pyqtSignal(list, bool)   # photos, cartoon_on

    def __init__(self):
        super().__init__()
        self.layout_name   = "세로4컷"
        self.needed        = 4
        self.captured      : list = []
        self.current_bgr   = None
        self.cam_thread    = None
        self.countdown_val = 0
        self.shooting      = False

        self.cd_timer = QTimer()
        self.cd_timer.timeout.connect(self._tick)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 12, 40, 12)
        root.setSpacing(8)

        step_lbl = QLabel("STEP 2 / 3")
        step_lbl.setObjectName("step")
        self.title_lbl = QLabel("촬영")
        self.title_lbl.setObjectName("title")
        root.addWidget(step_lbl, alignment=Qt.AlignCenter)
        root.addWidget(self.title_lbl, alignment=Qt.AlignCenter)

        # 카메라 뷰
        self.cam_lbl = QLabel()
        self.cam_lbl.setFixedSize(560, 400)
        self.cam_lbl.setAlignment(Qt.AlignCenter)
        self.cam_lbl.setStyleSheet(
            "background:#ede0ce; border:2px solid #e8c9a0; border-radius:8px;"
        )
        self.cam_lbl.setText("카메라 미리보기")

        # 플래시 오버레이 (cam_lbl 위에 겹쳐서 위치)
        self.flash_lbl = QLabel(self.cam_lbl)
        self.flash_lbl.setGeometry(0, 0, 560, 400)
        self.flash_lbl.setStyleSheet("background: rgba(255,255,255,200);")
        self.flash_lbl.hide()

        root.addWidget(self.cam_lbl, alignment=Qt.AlignCenter)

        # 진행 상태
        progress_row = QHBoxLayout()
        self.progress_lbl = QLabel("촬영 진행: 0 / ? 장")
        self.progress_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #e8c9a0;
                border: none;
                border-radius: 7px;
            }
            QProgressBar::chunk {
                background: #e85d1a;
                border-radius: 7px;
            }
        """)

        progress_row.addStretch()
        progress_row.addWidget(self.progress_lbl)
        progress_row.addSpacing(10)
        progress_row.addWidget(self.progress_bar)
        progress_row.addStretch()
        root.addLayout(progress_row)

        # 카툰 토글 + 버튼 한 행에 배치
        btn_row = QHBoxLayout()
        grp = QGroupBox("효과")
        grp_lay = QHBoxLayout(grp)
        grp_lay.setContentsMargins(8, 4, 8, 4)
        self.rb_cartoon_on  = QRadioButton("카툰 렌더링")
        self.rb_cartoon_off = QRadioButton("원본")
        self.rb_cartoon_off.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_cartoon_on,  0)
        bg.addButton(self.rb_cartoon_off, 1)
        grp_lay.addWidget(self.rb_cartoon_on)
        grp_lay.addWidget(self.rb_cartoon_off)
        btn_row.addStretch()
        btn_row.addWidget(grp)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── 직접 촬영 | 사진 선택 ──
        # 버튼 위젯 먼저 생성
        self.btn_cam   = QPushButton("📷  카메라 시작")
        self.btn_shoot = QPushButton("🎯  촬영 시작")
        self.btn_shoot.setObjectName("primary")
        self.btn_shoot.setEnabled(False)
        self.btn_stop  = QPushButton("⏹  촬영 중지")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setVisible(False)
        self.btn_file  = QPushButton("🖼  파일 선택")
        self.btn_file_next = QPushButton("다음  →")
        self.btn_file_next.setObjectName("primary")
        self.btn_file_next.setVisible(False)

        # 1행: 섹션 제목
        title_row = QHBoxLayout()
        lbl_direct = QLabel("직접 촬영")
        lbl_direct.setAlignment(Qt.AlignCenter)
        lbl_direct.setStyleSheet("font-weight:bold; color:#d94f1e; font-size:13px;")
        lbl_file = QLabel("사진 선택")
        lbl_file.setAlignment(Qt.AlignCenter)
        lbl_file.setStyleSheet("font-weight:bold; color:#d94f1e; font-size:13px;")
        title_row.addWidget(lbl_direct, stretch=3)
        title_row.addWidget(lbl_file, stretch=2)
        root.addLayout(title_row)

        # 2행: 버튼들
        all_btn_row = QHBoxLayout()
        all_btn_row.setSpacing(8)
        all_btn_row.addWidget(self.btn_cam)
        all_btn_row.addWidget(self.btn_shoot)
        all_btn_row.addWidget(self.btn_stop)
        all_btn_row.addSpacing(24)
        all_btn_row.addWidget(self.btn_file)
        all_btn_row.addWidget(self.btn_file_next)
        root.addLayout(all_btn_row)

        # 3행: 힌트 (직접 촬영 영역 비율에 맞게 가운데 정렬)
        hint_row = QHBoxLayout()
        hint_lbl = QLabel("(촬영 시작 전 카메라를 시작해주세요)")
        hint_lbl.setAlignment(Qt.AlignCenter)
        hint_lbl.setStyleSheet("font-size:13px; color:#b07040;")
        hint_row.addWidget(hint_lbl, stretch=3)
        hint_row.addStretch(2)
        root.addLayout(hint_row)

        # 썸네일 행 (사진마다 X 버튼)
        self.thumb_row = QHBoxLayout()
        self.thumb_row.setSpacing(8)
        self.thumb_row.setAlignment(Qt.AlignLeft)
        thumb_container = QWidget()
        thumb_container.setLayout(self.thumb_row)
        thumb_container.setStyleSheet("background:transparent;")
        root.addWidget(thumb_container)

        self.btn_cam.clicked.connect(self._toggle_camera)
        self.btn_shoot.clicked.connect(self._start_sequence)
        self.btn_stop.clicked.connect(self._stop_sequence)
        self.btn_file.clicked.connect(self._pick_files)
        self.btn_file_next.clicked.connect(self._file_done)

    # ── 레이아웃 설정 (Step1 → Step2 이동 시 호출) ──
    def setup(self, layout_name: str):
        self.layout_name = layout_name
        self.needed = {"세로4컷": 4, "가로3컷": 3, "단일": 1}[layout_name]
        self.captured.clear()
        self.btn_file_next.setVisible(False)
        self.title_lbl.setText(f"촬영  ({layout_name})")
        self._update_progress()

    # ── 카메라 ──
    def _toggle_camera(self):
        if self.cam_thread is None:
            self.cam_thread = CameraThread()
            self.cam_thread.frame_ready.connect(self._on_frame)
            self.cam_thread.start()
            self.btn_cam.setText("⏹  카메라 중지")
            self.btn_shoot.setEnabled(True)
        else:
            self._stop_camera()
            self.btn_shoot.setEnabled(False)

    def _stop_camera(self):
        if self.cam_thread:
            self.cam_thread.stop()
            self.cam_thread = None
        self.btn_cam.setText("📷  카메라 시작")
        self.cam_lbl.setText("카메라 미리보기")

    def _on_frame(self, bgr: np.ndarray):
        self.current_bgr = bgr
        display = apply_cartoon(bgr) if self.rb_cartoon_on.isChecked() else bgr
        if self.shooting and self.countdown_val > 0:
            display = draw_countdown(display, str(self.countdown_val))
        self.cam_lbl.setPixmap(bgr_to_pixmap(display, max_w=560, max_h=400))

    # ── 촬영 시퀀스 ──
    def _start_sequence(self):
        self.captured.clear()
        self.shooting = True
        self.btn_shoot.setVisible(False)
        self.btn_stop.setVisible(True)
        self.btn_file.setEnabled(False)
        self._next_shot()

    def _stop_sequence(self):
        self.cd_timer.stop()
        self.shooting = False
        self.captured.clear()
        self._update_progress()
        self.btn_stop.setVisible(False)
        self.btn_shoot.setVisible(True)
        self.btn_file.setEnabled(True)

    def _next_shot(self):
        if not self.shooting:
            return
        if len(self.captured) >= self.needed:
            self._sequence_done()
            return
        self.countdown_val = 3
        self.cd_timer.start(1000)

    def _tick(self):
        self.countdown_val -= 1
        if self.countdown_val > 0:
            return
        self.cd_timer.stop()
        self._snap()
        QTimer.singleShot(400, self._next_shot)

    def _snap(self):
        if self.current_bgr is None:
            return
        # 항상 원본 저장 (카툰은 미리보기에만 적용, Step3에서 결정)
        rgb = cv2.cvtColor(self.current_bgr.copy(), cv2.COLOR_BGR2RGB)
        self.captured.append(Image.fromarray(rgb))
        self._update_progress()
        # 플래시 효과
        self.flash_lbl.show()
        self.flash_lbl.raise_()
        QTimer.singleShot(300, self.flash_lbl.hide)

    def _sequence_done(self):
        self.shooting = False
        self.btn_stop.setVisible(False)
        self.btn_shoot.setVisible(True)
        self.btn_file.setEnabled(True)
        self._stop_camera()
        self.done_signal.emit(self.captured[:], self.rb_cartoon_on.isChecked())

    # ── 파일 선택 ──
    def _pick_files(self):
        remaining = self.needed - len(self.captured)
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            f"이미지 선택 (현재 {len(self.captured)}/{self.needed}장, {remaining}장 더 필요)",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not paths:
            return
        for p in paths:
            if len(self.captured) >= self.needed:
                break
            # 항상 원본 저장 (카툰은 Step3에서 결정)
            img = Image.open(p).convert("RGB")
            self.captured.append(img)
        self._update_progress()
        if len(self.captured) >= self.needed:
            self.btn_file_next.setVisible(True)

    def _file_done(self):
        self.btn_file_next.setVisible(False)
        self.done_signal.emit(self.captured[:], self.rb_cartoon_on.isChecked())

    def _update_progress(self):
        n = len(self.captured)
        self.progress_lbl.setText(f"촬영 진행: {n} / {self.needed} 장")
        self.progress_bar.setMaximum(self.needed)
        self.progress_bar.setValue(n)
        self._refresh_thumbnails()

    def _refresh_thumbnails(self):
        # 기존 썸네일 제거
        while self.thumb_row.count():
            item = self.thumb_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, img in enumerate(self.captured):
            # 카드 컨테이너
            card = QWidget()
            card.setStyleSheet("background:transparent;")
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(0, 0, 0, 0)
            card_lay.setSpacing(2)

            # 썸네일
            thumb = img.copy()
            thumb.thumbnail((70, 70))
            qi = QImage(thumb.tobytes(), thumb.width, thumb.height,
                        thumb.width * 3, QImage.Format_RGB888)
            img_lbl = QLabel()
            img_lbl.setPixmap(QPixmap.fromImage(qi))
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setStyleSheet(
                "border:1px solid #e8c9a0; border-radius:4px; background:#fdf7ee;"
            )

            # X 버튼
            del_btn = QPushButton("✕")
            del_btn.setFixedHeight(20)
            del_btn.setStyleSheet("""
                QPushButton {
                    background:#f38ba8; color:#fff; border:none;
                    border-radius:4px; font-size:11px; padding:0;
                }
                QPushButton:hover { background:#c0392b; }
            """)
            del_btn.clicked.connect(lambda _, idx=i: self._delete_photo(idx))

            card_lay.addWidget(img_lbl)
            card_lay.addWidget(del_btn)
            self.thumb_row.addWidget(card)

    def _delete_photo(self, idx: int):
        if 0 <= idx < len(self.captured):
            self.captured.pop(idx)
            self.btn_file_next.setVisible(False)
            self._update_progress()

    def cleanup(self):
        self.cd_timer.stop()
        self._stop_camera()
        self.shooting = False


# ══════════════════════════════════════════════════════════════
# Step 3 – 프레임 색상 선택 + 저장
# ══════════════════════════════════════════════════════════════
class Step3Widget(QWidget):
    restart_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.photos          : list = []
        self.original_photos : list = []   # 원본 보관
        self.layout_name     : str  = "세로4컷"

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(40, 24, 40, 24)
        self.root.setSpacing(16)

        # ── 헤더 ──
        step_lbl = QLabel("STEP 3 / 3")
        step_lbl.setObjectName("step")
        title = QLabel("프레임 색상 선택")
        title.setObjectName("title")
        self.root.addWidget(step_lbl, alignment=Qt.AlignCenter)
        self.root.addWidget(title,    alignment=Qt.AlignCenter)

        # ── 색상 선택 그룹 (재사용) ──
        self.color_grp = QGroupBox("색상")
        grp_lay = QVBoxLayout(self.color_grp)
        grp_lay.setSpacing(12)
        self.color_bg = QButtonGroup()
        for i, name in enumerate(FRAME_COLORS):
            rb = QRadioButton(f"  {name}")
            if i == 0:
                rb.setChecked(True)
            self.color_bg.addButton(rb, i)
            grp_lay.addWidget(rb)
        self.color_bg.buttonClicked.connect(self._refresh_preview)

        # ── 효과 선택 그룹 (재사용) ──
        self.effect_grp = QGroupBox("효과")
        eff_lay = QVBoxLayout(self.effect_grp)
        eff_lay.setSpacing(12)
        self.effect_bg = QButtonGroup()
        self.rb_orig    = QRadioButton("  원본")
        self.rb_cartoon = QRadioButton("  카툰 렌더링")
        self.rb_orig.setChecked(True)
        self.effect_bg.addButton(self.rb_orig,    0)
        self.effect_bg.addButton(self.rb_cartoon, 1)
        eff_lay.addWidget(self.rb_orig)
        eff_lay.addWidget(self.rb_cartoon)
        self.effect_bg.buttonClicked.connect(self._on_effect_changed)

        # ── 미리보기 라벨 (재사용) ──
        self.preview_lbl = QLabel()
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setStyleSheet(
            "border:1px solid #e8c9a0; border-radius:8px; padding:4px; background:#fdf7ee;"
        )

        # ── 콘텐츠 컨테이너 (레이아웃에 따라 교체) ──
        self.content_widget = QWidget()
        self.root.addWidget(self.content_widget, stretch=1)

        # ── 푸터 버튼 ──
        btn_row = QHBoxLayout()
        self.btn_restart = QPushButton("🔄  처음으로")
        self.btn_restart.setFixedHeight(44)
        self.btn_save = QPushButton("💾  저장")
        self.btn_save.setObjectName("primary")
        self.btn_save.setFixedHeight(44)
        btn_row.addWidget(self.btn_restart)
        btn_row.addWidget(self.btn_save)
        self.root.addLayout(btn_row)

        self.btn_save.clicked.connect(self._save)
        self.btn_restart.clicked.connect(self.restart_signal.emit)

    def _rebuild_content(self):
        """레이아웃 종류에 따라 콘텐츠 영역을 수평/수직으로 재구성"""
        # 기존 레이아웃 제거
        old = self.content_widget.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            QWidget().setLayout(old)  # old layout 해제

        if self.layout_name == "가로3컷":
            # 위: (색상 + 효과) / 아래: 미리보기
            lay = QVBoxLayout(self.content_widget)
            lay.setSpacing(16)
            opt_row = QHBoxLayout()
            opt_row.addStretch()
            opt_row.addWidget(self.color_grp)
            opt_row.addWidget(self.effect_grp)
            opt_row.addStretch()
            lay.addLayout(opt_row)
            lay.addWidget(self.preview_lbl, stretch=1)
        else:
            # 왼쪽: (색상 + 효과) / 오른쪽: 미리보기
            lay = QHBoxLayout(self.content_widget)
            lay.setSpacing(24)
            left = QVBoxLayout()
            left.addWidget(self.color_grp)
            left.addWidget(self.effect_grp)
            left.addStretch()
            lay.addLayout(left, stretch=0)
            lay.addWidget(self.preview_lbl, stretch=1)

    def setup(self, photos: list, layout_name: str):
        self.original_photos = [p.copy() for p in photos]
        self.photos          = photos
        self.layout_name     = layout_name
        self.rb_orig.setChecked(True)   # 항상 원본으로 초기화
        self._rebuild_content()
        self._refresh_preview()

    def _selected_color(self) -> str:
        return list(FRAME_COLORS.keys())[self.color_bg.checkedId()]

    def _on_effect_changed(self):
        if self.rb_cartoon.isChecked():
            self.photos = []
            for img in self.original_photos:
                arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                arr = apply_cartoon(arr)
                self.photos.append(Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)))
        else:
            self.photos = [p.copy() for p in self.original_photos]
        self._refresh_preview()

    def _refresh_preview(self):
        if not self.photos:
            return
        img = build_frame(self.photos, self.layout_name, self._selected_color())
        if self.layout_name == "가로3컷":
            img.thumbnail((700, 400))
        else:
            img.thumbnail((360, 680))
        arr = np.array(img)
        qi  = QImage(arr.data, arr.shape[1], arr.shape[0],
                     arr.shape[1] * 3, QImage.Format_RGB888)
        self.preview_lbl.setPixmap(QPixmap.fromImage(qi))

    def _save(self):
        result = build_frame(self.photos, self.layout_name, self._selected_color())
        ts = datetime.now().strftime("%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, "저장 위치 선택", f"CartoonBooth_{ts}.png",
            "PNG (*.png);;JPEG (*.jpg)"
        )
        if path:
            result.save(path)


# ══════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════
class InssaengApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cartoon Booth! 📸")
        self.setMinimumSize(800, 720)
        self.setStyleSheet(STYLE)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.step1 = Step1Widget()
        self.step2 = Step2Widget()
        self.step3 = Step3Widget()

        self.stack.addWidget(self.step1)   # index 0
        self.stack.addWidget(self.step2)   # index 1
        self.stack.addWidget(self.step3)   # index 2

        self.step1.next_signal.connect(self._go_step2)
        self.step2.done_signal.connect(self._go_step3)
        self.step3.restart_signal.connect(self._go_step1)

    def _go_step2(self, layout_name: str):
        self.step2.setup(layout_name)
        self.stack.setCurrentIndex(1)

    def _go_step3(self, photos: list, _: bool):
        layout = self.step2.layout_name
        self.step3.setup(photos, layout)
        self.stack.setCurrentIndex(2)

    def _go_step1(self):
        self.step2.cleanup()
        self.stack.setCurrentIndex(0)

    def closeEvent(self, event):
        self.step2.cleanup()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = InssaengApp()
    win.show()
    sys.exit(app.exec_())
