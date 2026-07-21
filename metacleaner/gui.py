# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .engine import SUPPORTED_EXTENSIONS, category_for, clean_file, inspect_file, iter_supported_files
from .models import CleanMode, CleanOptions, CleanResult, InspectionResult


APP_NAME = "文档隐私清理器"


STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
    color: #263238;
}
QMainWindow, QWidget#central {
    background: #f4f7f9;
}
QFrame#hero {
    background: #173f5f;
    border-radius: 10px;
}
QLabel#heroTitle {
    color: white;
    font-size: 24px;
    font-weight: 700;
}
QLabel#heroSubtitle {
    color: #dceaf4;
    font-size: 13px;
}
QFrame#card {
    background: white;
    border: 1px solid #d8e1e8;
    border-radius: 9px;
}
QLabel#sectionTitle {
    color: #173f5f;
    font-size: 15px;
    font-weight: 700;
}
QPushButton {
    min-height: 32px;
    padding: 0 14px;
    border: 1px solid #b8c7d2;
    border-radius: 6px;
    background: #ffffff;
}
QPushButton:hover { background: #eef5f9; border-color: #6d95ad; }
QPushButton:disabled { color: #98a4ab; background: #edf0f2; }
QPushButton#primary {
    background: #1f6f8b;
    border-color: #1f6f8b;
    color: white;
    font-weight: 700;
    min-height: 38px;
}
QPushButton#primary:hover { background: #185d75; }
QPushButton#danger { color: #a33a3a; }
QTableWidget {
    background: white;
    border: 1px solid #d8e1e8;
    border-radius: 6px;
    gridline-color: #e7edf1;
    selection-background-color: #d9ecf5;
    selection-color: #263238;
}
QHeaderView::section {
    background: #e9f1f5;
    border: none;
    border-right: 1px solid #d8e1e8;
    border-bottom: 1px solid #c5d2da;
    padding: 8px;
    color: #284b63;
    font-weight: 700;
}
QLineEdit, QComboBox, QTextEdit {
    background: white;
    border: 1px solid #c7d3db;
    border-radius: 5px;
    padding: 6px;
}
QLineEdit:disabled { background: #edf0f2; }
QTextEdit { font-family: "Consolas", "Microsoft YaHei UI"; font-size: 12px; }
QProgressBar {
    border: 1px solid #c7d3db;
    border-radius: 5px;
    background: #edf2f5;
    text-align: center;
    min-height: 20px;
}
QProgressBar::chunk { background: #2a9d8f; border-radius: 4px; }
QCheckBox, QRadioButton { spacing: 8px; }
"""


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#173f5f"), 3))
    painter.setBrush(QColor("#d7eef3"))
    path = QPainterPath()
    path.moveTo(32, 5)
    path.lineTo(54, 13)
    path.lineTo(51, 37)
    path.cubicTo(49, 49, 40, 56, 32, 60)
    path.cubicTo(24, 56, 15, 49, 13, 37)
    path.lineTo(10, 13)
    path.closeSubpath()
    painter.drawPath(path)
    painter.setPen(QPen(QColor("#1f6f8b"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(22, 33, 29, 40)
    painter.drawLine(29, 40, 44, 23)
    painter.end()
    return QIcon(pixmap)


class InspectSignals(QObject):
    item = Signal(str, object)
    finished = Signal()


class InspectWorker(QRunnable):
    def __init__(self, paths: list[Path]):
        super().__init__()
        self.paths = paths
        self.signals = InspectSignals()

    def run(self):
        try:
            for path in self.paths:
                try:
                    result = inspect_file(path)
                except Exception as exc:
                    result = InspectionResult(
                        path,
                        category_for(path),
                        False,
                        warnings=[f"检测过程中发生异常：{exc}"],
                    )
                self.signals.item.emit(str(path), result)
        finally:
            self.signals.finished.emit()


class CleanSignals(QObject):
    progress = Signal(int, int, str)
    item = Signal(str, object)
    finished = Signal()


class CleanWorker(QRunnable):
    def __init__(self, paths: list[Path], output_dir: Path | None, options: CleanOptions):
        super().__init__()
        self.paths = paths
        self.output_dir = output_dir
        self.options = options
        self.signals = CleanSignals()

    def run(self):
        total = len(self.paths)
        try:
            for index, path in enumerate(self.paths, 1):
                self.signals.progress.emit(index - 1, total, path.name)
                try:
                    result = clean_file(path, self.output_dir, self.options)
                except Exception as exc:
                    result = CleanResult(path, None, False, error=f"处理过程中发生异常：{exc}")
                self.signals.item.emit(str(path), result)
                self.signals.progress.emit(index, total, path.name)
        finally:
            self.signals.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1180, 780)
        self.setMinimumSize(980, 680)
        self.setAcceptDrops(True)
        self.thread_pool = QThreadPool.globalInstance()
        self.paths: list[Path] = []
        self.row_for_path: dict[Path, int] = {}
        self.inspections: dict[Path, InspectionResult] = {}
        self.outputs: dict[Path, Path] = {}
        self.clean_successes = 0
        self.clean_review_needed = 0
        self.pending_inspections = 0
        self.busy = False
        self.settings = QSettings("CodexTools", "DocumentPrivacyCleaner")

        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        root.addWidget(self._build_hero())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_file_card())
        splitter.addWidget(self._build_settings_card())
        splitter.setSizes([790, 350])
        root.addWidget(splitter, 1)

        self._restore_settings()
        self._update_controls()

    def _build_hero(self) -> QFrame:
        frame = QFrame(objectName="hero")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(22, 16, 22, 16)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(52, 52))
        layout.addWidget(icon)
        text = QVBoxLayout()
        title = QLabel("文档隐私清理器", objectName="heroTitle")
        subtitle = QLabel("批量清除作者、修改者、时间、公司、自定义属性及审阅者等文件元数据；始终生成副本。", objectName="heroSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(subtitle)
        layout.addLayout(text, 1)
        badge = QLabel("本地处理 · 不上传")
        badge.setStyleSheet("color:#173f5f; background:#d9f0e8; padding:7px 11px; border-radius:12px; font-weight:700;")
        layout.addWidget(badge)
        return frame

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame(objectName="card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        return frame, layout

    def _build_file_card(self) -> QFrame:
        frame, layout = self._card()
        header = QHBoxLayout()
        header.addWidget(QLabel("待处理文件", objectName="sectionTitle"))
        header.addStretch()
        self.add_files_button = QPushButton("添加文件")
        self.add_folder_button = QPushButton("添加文件夹")
        self.remove_button = QPushButton("移除选中", objectName="danger")
        self.clear_button = QPushButton("清空")
        self.add_files_button.clicked.connect(self.choose_files)
        self.add_folder_button.clicked.connect(self.choose_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_files)
        for button in (self.add_files_button, self.add_folder_button, self.remove_button, self.clear_button):
            header.addWidget(button)
        layout.addLayout(header)

        hint = QLabel("可拖入文件或文件夹。支持 Office 新格式、PDF、ODT/ODS/ODP，以及 JPG/PNG/TIFF/WebP。旧版 .doc/.xls/.ppt 会安全跳过。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#607d8b;")
        layout.addWidget(hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件名", "类型", "检测结果", "状态", "输出文件"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.show_row_details)
        layout.addWidget(self.table, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("等待文件")
        layout.addWidget(self.progress)
        return frame

    def _build_settings_card(self) -> QFrame:
        frame, layout = self._card()
        layout.addWidget(QLabel("清理设置", objectName="sectionTitle"))

        layout.addWidget(QLabel("清理范围"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("仅个人信息（推荐）", CleanMode.PERSONAL)
        self.mode_combo.addItem("全部文档属性", CleanMode.ALL)
        self.mode_combo.setToolTip("全部文档属性模式还会移除标题、主题、关键词和应用程序属性。")
        layout.addWidget(self.mode_combo)

        self.review_check = QCheckBox("匿名化批注与修订作者")
        self.review_check.setChecked(True)
        self.thumbnail_check = QCheckBox("删除 Office 文档缩略图")
        self.thumbnail_check.setChecked(True)
        self.verify_check = QCheckBox("清理后复检残留元数据")
        self.verify_check.setChecked(True)
        for check in (self.review_check, self.thumbnail_check, self.verify_check):
            layout.addWidget(check)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color:#d8e1e8;")
        layout.addWidget(divider)

        layout.addWidget(QLabel("输出位置"))
        self.same_folder_radio = QRadioButton("原文件旁生成 _clean 副本")
        self.custom_folder_radio = QRadioButton("输出到指定文件夹")
        self.same_folder_radio.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.same_folder_radio)
        group.addButton(self.custom_folder_radio)
        layout.addWidget(self.same_folder_radio)
        layout.addWidget(self.custom_folder_radio)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择输出文件夹")
        self.output_button = QPushButton("浏览")
        self.output_button.clicked.connect(self.choose_output_folder)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)
        layout.addLayout(output_row)
        self.same_folder_radio.toggled.connect(self._update_output_controls)

        note = QLabel("安全规则：不覆盖原文件；加密文件、数字签名文件和不支持的旧版 Office 文件会跳过。图片会重新编码。")
        note.setWordWrap(True)
        note.setStyleSheet("background:#fff6dd; color:#7a5714; border:1px solid #ead79b; padding:9px; border-radius:6px;")
        layout.addWidget(note)

        self.clean_button = QPushButton("开始清理", objectName="primary")
        self.clean_button.clicked.connect(self.start_cleaning)
        layout.addWidget(self.clean_button)

        layout.addWidget(QLabel("处理日志", objectName="sectionTitle"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("检测和清理结果会显示在这里。")
        layout.addWidget(self.log, 1)

        help_row = QHBoxLayout()
        self.open_output_button = QPushButton("打开最近输出目录")
        self.open_output_button.clicked.connect(self.open_recent_output)
        about_button = QPushButton("说明")
        about_button.clicked.connect(self.show_about)
        help_row.addWidget(self.open_output_button)
        help_row.addWidget(about_button)
        layout.addLayout(help_row)
        return frame

    def _restore_settings(self):
        self.output_edit.setText(self.settings.value("output_dir", ""))
        self.mode_combo.setCurrentIndex(int(self.settings.value("mode_index", 0)))
        self.review_check.setChecked(self.settings.value("review", True, bool))
        self.thumbnail_check.setChecked(self.settings.value("thumbnail", True, bool))
        self.verify_check.setChecked(self.settings.value("verify", True, bool))
        self._update_output_controls()

    def _save_settings(self):
        self.settings.setValue("output_dir", self.output_edit.text())
        self.settings.setValue("mode_index", self.mode_combo.currentIndex())
        self.settings.setValue("review", self.review_check.isChecked())
        self.settings.setValue("thumbnail", self.thumbnail_check.isChecked())
        self.settings.setValue("verify", self.verify_check.isChecked())

    def closeEvent(self, event):
        if self.busy or self.pending_inspections:
            QMessageBox.warning(self, APP_NAME, "文件仍在检测或处理，请等待当前任务完成后再关闭。")
            event.ignore()
            return
        self._save_settings()
        super().closeEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_paths(paths)
        event.acceptProposedAction()

    def choose_files(self):
        filters = "支持的文件 (*.docx *.docm *.dotx *.dotm *.xlsx *.xlsm *.xltx *.xltm *.pptx *.pptm *.potx *.potm *.ppsx *.ppsm *.pdf *.odt *.ods *.odp *.odg *.jpg *.jpeg *.png *.tif *.tiff *.webp);;所有文件 (*.*)"
        names, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", filters)
        self.add_paths(Path(name) for name in names)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.add_paths([Path(folder)])

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹", self.output_edit.text())
        if folder:
            self.output_edit.setText(folder)
            self.custom_folder_radio.setChecked(True)

    def add_paths(self, paths: Iterable[Path]):
        if self.busy:
            return
        files: list[Path] = []
        for raw in paths:
            path = raw.expanduser().resolve()
            if path.is_dir():
                files.extend(iter_supported_files(path, recursive=True))
            elif path.is_file():
                files.append(path)
        new_paths = []
        for path in files:
            if path in self.row_for_path:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.paths.append(path)
            self.row_for_path[path] = row
            name_item = QTableWidgetItem(path.name)
            name_item.setToolTip(str(path))
            name_item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(category_for(path)))
            self.table.setItem(row, 2, QTableWidgetItem("检测中…"))
            self.table.setItem(row, 3, QTableWidgetItem("等待"))
            self.table.setItem(row, 4, QTableWidgetItem(""))
            new_paths.append(path)
        if new_paths:
            self.pending_inspections += 1
            worker = InspectWorker(new_paths)
            worker.signals.item.connect(self._inspection_ready)
            worker.signals.finished.connect(self._inspection_finished)
            self.thread_pool.start(worker)
            self.log.append(f"已添加 {len(new_paths)} 个文件，正在检测元数据…")
        elif files:
            self.log.append("所选文件已在列表中。")
        self._update_controls()

    def _inspection_ready(self, path_text: str, result: InspectionResult):
        path = Path(path_text)
        self.inspections[path] = result
        row = self.row_for_path.get(path)
        if row is None:
            return
        self.table.item(row, 1).setText(result.category)
        self.table.item(row, 2).setText(result.summary)
        details = [f"{i.group} · {i.name}: {i.value}" for i in result.items]
        details.extend(result.warnings)
        self.table.item(row, 2).setToolTip("\n".join(details) or "未发现已知元数据")
        status = "可处理" if result.supported and not result.signed and not result.encrypted else "将跳过"
        self.table.item(row, 3).setText(status)
        if status == "将跳过":
            self.table.item(row, 3).setForeground(QColor("#b04a3a"))

    def _inspection_finished(self):
        self.pending_inspections = max(0, self.pending_inspections - 1)
        if self.pending_inspections == 0:
            supported = sum(1 for result in self.inspections.values() if result.supported and not result.signed and not result.encrypted)
            self.log.append(f"检测完成：{supported} 个文件可安全处理。")
        self._update_controls()

    def remove_selected(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            path_text = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            path = Path(path_text)
            self.table.removeRow(row)
            self.paths.remove(path)
            self.inspections.pop(path, None)
            self.outputs.pop(path, None)
        self._rebuild_row_map()
        self._update_controls()

    def clear_files(self):
        if self.busy:
            return
        self.table.setRowCount(0)
        self.paths.clear()
        self.row_for_path.clear()
        self.inspections.clear()
        self.outputs.clear()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("等待文件")
        self._update_controls()

    def _rebuild_row_map(self):
        self.row_for_path.clear()
        for row in range(self.table.rowCount()):
            path = Path(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
            self.row_for_path[path] = row

    def _update_output_controls(self):
        custom = self.custom_folder_radio.isChecked()
        self.output_edit.setEnabled(custom)
        self.output_button.setEnabled(custom)

    def _update_controls(self):
        idle = not self.busy and self.pending_inspections == 0
        ready = bool(self.paths) and idle
        self.clean_button.setEnabled(ready)
        self.add_files_button.setEnabled(idle)
        self.add_folder_button.setEnabled(idle)
        self.remove_button.setEnabled(bool(self.paths) and idle)
        self.clear_button.setEnabled(bool(self.paths) and idle)
        self.open_output_button.setEnabled(bool(self.outputs))

    def start_cleaning(self):
        if self.custom_folder_radio.isChecked():
            text = self.output_edit.text().strip()
            if not text:
                QMessageBox.warning(self, APP_NAME, "请先选择输出文件夹。")
                return
            output_dir = Path(text)
        else:
            output_dir = None
        mode = self.mode_combo.currentData()
        options = CleanOptions(
            mode=mode,
            anonymize_reviewers=self.review_check.isChecked(),
            remove_thumbnail=self.thumbnail_check.isChecked(),
            verify_after_clean=self.verify_check.isChecked(),
        )
        self._save_settings()
        self.busy = True
        self.outputs.clear()
        self.clean_successes = 0
        self.clean_review_needed = 0
        self.progress.setRange(0, len(self.paths))
        self.progress.setValue(0)
        self.log.append(f"开始处理 {len(self.paths)} 个文件；模式：{'仅个人信息' if mode == CleanMode.PERSONAL else '全部文档属性'}。")
        for path in self.paths:
            row = self.row_for_path[path]
            self.table.item(row, 3).setText("处理中…")
            self.table.item(row, 4).setText("")
        worker = CleanWorker(list(self.paths), output_dir, options)
        worker.signals.progress.connect(self._clean_progress)
        worker.signals.item.connect(self._clean_item)
        worker.signals.finished.connect(self._clean_finished)
        self.thread_pool.start(worker)
        self._update_controls()

    def _clean_progress(self, value: int, total: int, name: str):
        self.progress.setRange(0, total)
        self.progress.setValue(value)
        self.progress.setFormat(f"{value}/{total}  {name}")

    def _clean_item(self, path_text: str, result: CleanResult):
        path = Path(path_text)
        row = self.row_for_path.get(path)
        if row is None:
            return
        if result.output:
            self.outputs[path] = result.output
            self.table.item(row, 4).setText(str(result.output))
            self.table.item(row, 4).setToolTip(str(result.output))
            if result.success:
                self.clean_successes += 1
                status = "已清理" if self.verify_check.isChecked() else "已清理（未复检）"
                self.table.item(row, 3).setText(status)
                self.table.item(row, 3).setForeground(QColor("#19734c"))
                self.log.append(f"✓ {path.name} → {result.output.name}（清除/匿名化 {result.removed_count} 项）")
            else:
                self.clean_review_needed += 1
                self.table.item(row, 3).setText("已输出，需复核")
                self.table.item(row, 3).setForeground(QColor("#a36a00"))
                message = result.error or "复检仍发现所选范围内的元数据"
                if result.residual_items:
                    names = "、".join(f"{item.group}/{item.name}" for item in result.residual_items[:5])
                    message += f"：{names}"
                self.log.append(f"! {path.name} → {result.output.name}：{message}")
        else:
            self.table.item(row, 3).setText("失败/跳过")
            self.table.item(row, 3).setForeground(QColor("#b04a3a"))
            message = result.error or "清理后仍检测到残留元数据"
            if result.residual_items:
                names = "、".join(f"{item.group}/{item.name}" for item in result.residual_items[:5])
                message += f"：{names}"
            self.log.append(f"✗ {path.name}：{message}")
        for warning in result.warnings:
            self.log.append(f"  提示：{warning}")

    def _clean_finished(self):
        self.busy = False
        success = self.clean_successes
        review_needed = self.clean_review_needed
        total = len(self.paths)
        failed = total - success - review_needed
        self.progress.setValue(total)
        self.progress.setFormat(f"完成：成功 {success} / 总计 {total}")
        self.log.append(f"处理完成：成功 {success} 个，需复核 {review_needed} 个，失败或跳过 {failed} 个。")
        self._update_controls()
        QMessageBox.information(
            self,
            APP_NAME,
            f"处理完成。\n成功：{success}\n已输出但需复核：{review_needed}\n失败或跳过：{failed}\n\n原文件均未覆盖。",
        )

    def show_row_details(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        path = Path(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        if path in self.outputs:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.outputs[path].parent)))
            return
        result = self.inspections.get(path)
        if not result:
            return
        lines = [str(path), "", f"类型：{result.category}", f"状态：{result.summary}"]
        if result.items:
            lines.append("")
            lines.append("检测到：")
            lines.extend(f"• {item.group} / {item.name}: {item.value}" for item in result.items)
        if result.warnings:
            lines.append("")
            lines.append("提示：")
            lines.extend(f"• {warning}" for warning in result.warnings)
        QMessageBox.information(self, "元数据详情", "\n".join(lines))

    def open_recent_output(self):
        if not self.outputs:
            return
        latest = list(self.outputs.values())[-1]
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(latest.parent)))

    def show_about(self):
        QMessageBox.information(
            self,
            f"关于 {APP_NAME}",
            f"{APP_NAME} {__version__}\n\n"
            "支持：Office OOXML、PDF、OpenDocument、常见静态图片。\n"
            "不支持：旧版 .doc/.xls/.ppt、加密文件、动画图片。\n"
            "数字签名文件会跳过；PDF 嵌入附件不会递归处理。\n\n"
            "所有处理均在本机完成，默认生成 _clean 副本。\n\n"
            "Copyright (C) 2026 Carota-Bunny\n"
            "GNU AGPL v3；不提供任何担保。\n"
            "源码：https://github.com/Carota-Bunny/document-privacy-cleaner",
        )


def run_app(smoke_test: bool = False) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("CodexTools")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if smoke_test:
        QTimer.singleShot(800, app.quit)
    return app.exec()
