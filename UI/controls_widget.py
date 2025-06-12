from PyQt5.QtWidgets import QWidget, QPushButton, QFileDialog, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal

class ControlsWidget(QWidget):
    
    start_recording = pyqtSignal()
    pause_recording = pyqtSignal()
    save_recording = pyqtSignal()
    video_processing = pyqtSignal()
    replay_video = pyqtSignal()
    export_report = pyqtSignal()
    video_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # 綠色樣式 + Calibri 字體
        button_style = """
        QPushButton {
            background-color: #2E7D32;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-family: Calibri;
        }
        QPushButton:hover {
            background-color: #7CB342;
        }
        QLabel {
            font-family: Calibri;
            font-size: 18px;
            font-weight: bold;
        }
        """

        # Real-time 區塊
        realtime_label = QLabel("Real-time")
        self.btn_start_recording = QPushButton("Start recording")
        self.btn_pause_recording = QPushButton("Stop recording")
        self.btn_video_processing = QPushButton("Video processing")

        for btn in [self.btn_start_recording, self.btn_pause_recording, self.btn_video_processing]:
            btn.setStyleSheet(button_style)

        # Replay 區塊
        replay_label = QLabel("Replay")
        self.btn_choose_video = QPushButton("Choose video")
        self.btn_export_report = QPushButton("Export report")

        for btn in [self.btn_choose_video, self.btn_export_report]:
            btn.setStyleSheet(button_style)

        # layout 排版
        layout = QVBoxLayout()
        layout.addWidget(realtime_label)
        layout.addWidget(self.btn_start_recording)
        layout.addWidget(self.btn_pause_recording)
        layout.addWidget(self.btn_video_processing)

        layout.addSpacing(20)
        layout.addWidget(replay_label)
        layout.addWidget(self.btn_choose_video)
        layout.addWidget(self.btn_export_report)
        layout.addStretch()

        self.setLayout(layout)

        # Connect signals
        self.btn_start_recording.clicked.connect(self.start_recording.emit)
        self.btn_pause_recording.clicked.connect(self.pause_recording.emit)
        self.btn_video_processing.clicked.connect(self.video_processing.emit)
        self.btn_export_report.clicked.connect(self.export_report.emit)
        self.btn_choose_video.clicked.connect(self.open_file_dialog)

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇影片", "", "Video Files (*.mp4 *.avi)")
        if path:
            self.video_selected.emit(path)
