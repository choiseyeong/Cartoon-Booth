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
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap


# ── main.py와 동일한 카툰 렌더링 ──────────────────────────────
def apply_cartoon(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    small = cv2.resize(bgr, (w * 3 // 4, h * 3 // 4))

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    edges = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY, blockSize=15, C=8
    )
    edges = cv2.medianBlur(edges, 3)

    color = cv2.bilateralFilter(small, 5, 25, 25)

    hsv = cv2.cvtColor(color, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.5, 0, 255)
    color = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    cartoon_small = cv2.bitwise_and(color, color, mask=edges)
    return cv2.resize(cartoon_small, (w, h))


def pil_to_pixmap(img: Image.Image, max_w=600, max_h=500) -> QPixmap:
    arr = np.array(img)
    qi = QImage(arr.data, arr.shape[1], arr.shape[0],
                arr.shape[1] * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qi).scaled(
        max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )


# ── UI ────────────────────────────────────────────────────────
class CartoonTestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("카툰 렌더링 테스트")
        self.setMinimumSize(860, 620)
        self.setStyleSheet("background:#f5f0e8; color:#3b2a1a; font-family:'Malgun Gothic';")

        self.result_img: Image.Image | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # 미리보기: 원본(위) / 결과(아래) — 가로 이미지 최적화
        self.lbl_original = self._make_preview_label("원본")
        self.lbl_cartoon  = self._make_preview_label("카툰 렌더링 결과")
        root.addWidget(self.lbl_original, stretch=1)
        root.addWidget(self.lbl_cartoon,  stretch=1)

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_open = QPushButton("📂  파일 선택")
        self.btn_open.setStyleSheet(self._btn_style())
        self.btn_open.setFixedHeight(44)

        self.btn_save = QPushButton("💾  결과 저장")
        self.btn_save.setStyleSheet(self._btn_primary_style())
        self.btn_save.setFixedHeight(44)
        self.btn_save.setEnabled(False)

        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

        self.btn_open.clicked.connect(self._open_file)
        self.btn_save.clicked.connect(self._save_result)

    def _make_preview_label(self, title: str) -> QLabel:
        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(wrapper)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:#d94f1e;")

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setMinimumSize(800, 220)
        img_lbl.setStyleSheet(
            "background:#fdf7ee; border:1px solid #e8c9a0; border-radius:8px;"
        )

        lay.addWidget(title_lbl)
        lay.addWidget(img_lbl, stretch=1)

        # img_lbl을 반환하기 위해 wrapper에 속성으로 저장
        wrapper.img_lbl = img_lbl
        return wrapper

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 선택", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return

        original = Image.open(path).convert("RGB")

        # 원본 표시
        self.lbl_original.img_lbl.setPixmap(pil_to_pixmap(original, max_w=820, max_h=240))

        # 카툰 적용
        bgr = cv2.cvtColor(np.array(original), cv2.COLOR_RGB2BGR)
        cartoon_bgr = apply_cartoon(bgr)
        cartoon_rgb = cv2.cvtColor(cartoon_bgr, cv2.COLOR_BGR2RGB)
        self.result_img = Image.fromarray(cartoon_rgb)

        # 결과 표시
        self.lbl_cartoon.img_lbl.setPixmap(pil_to_pixmap(self.result_img, max_w=820, max_h=240))
        self.btn_save.setEnabled(True)

    def _save_result(self):
        if self.result_img is None:
            return
        ts = datetime.now().strftime("%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, "저장 위치 선택", f"cartoon_result_{ts}.png",
            "PNG (*.png);;JPEG (*.jpg)"
        )
        if path:
            self.result_img.save(path)

    def _btn_style(self):
        return """
            QPushButton { background:#fdebd8; border:1px solid #e8c9a0;
                          border-radius:8px; padding:8px 20px; }
            QPushButton:hover { background:#fad9b8; }
        """

    def _btn_primary_style(self):
        return """
            QPushButton { background:#e85d1a; color:#fff7f0; font-weight:bold;
                          border:none; border-radius:8px; padding:8px 20px; }
            QPushButton:hover { background:#d94f10; }
            QPushButton:disabled { background:#e8c9a0; color:#b07040; }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CartoonTestWindow()
    win.show()
    sys.exit(app.exec_())
