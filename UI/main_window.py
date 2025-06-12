from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QMessageBox, QLabel, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal
from UI.controls_widget import ControlsWidget
from UI.video_player_widget import VideoPlayerWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SwimAnalysisPro 智慧泳池系統")
        self.resize(1280, 800)

        self.video_player = VideoPlayerWidget()
        self.controls = ControlsWidget()

        # 初始播放狀態：尚未播放
        self.is_playing = False

        # 播放/暫停按鈕，初始為「▶」
        self.btn_toggle_play = QPushButton("▶")
        self.btn_toggle_play.setFixedSize(40, 40)
        btn_style = """
        QPushButton {
            background-color: rgba(33, 150, 243, 0.5);  /* 淺藍 + 透明度 */
            color: white;
            border: 1px solid white;  /* 如果你希望邊框仍有，可以保留這行 */
            border-radius: 8px;
            font-size: 18px;
            font-family: Calibri;
        }
        QPushButton:hover {
            background-color: rgba(255, 255, 255, 0.1);  /* 滑鼠移過去可淡顯示背景 */
        }
        """
        self.btn_toggle_play.setStyleSheet(btn_style)

        self.init_ui()

        # 連接 signals
        self.controls.start_recording.connect(self.start_recording)
        self.controls.pause_recording.connect(self.pause_recording)
        self.controls.save_recording.connect(self.save_recording)
        self.controls.video_processing.connect(self.run_video_processing)
        self.controls.replay_video.connect(self.replay_existing_analysis)
        self.controls.export_report.connect(self.export_report)
        self.controls.video_selected.connect(self.video_selected)
        self.btn_toggle_play.clicked.connect(self.toggle_play)

    def init_ui(self):
        layout = QVBoxLayout()

        # Video area
        layout.addWidget(self.video_player)

        # Real-time Control Row
        realtime_row = QHBoxLayout()
        realtime_label = QLabel("Real-time")
        realtime_label.setStyleSheet("font-weight: bold; padding-right: 10px;")
        realtime_row.addWidget(realtime_label)
        realtime_row.addWidget(self.controls.btn_start_recording)
        realtime_row.addWidget(self.controls.btn_pause_recording)
        realtime_row.addWidget(self.controls.btn_video_processing)
        layout.addLayout(realtime_row)

        # Replay Control Row
        replay_row = QHBoxLayout()
        replay_label = QLabel("Replay")
        replay_label.setStyleSheet("font-weight: bold; padding-right: 10px;")
        replay_row.addWidget(replay_label)
        replay_row.addWidget(self.controls.btn_choose_video)
        replay_row.addWidget(self.controls.btn_export_report)
        layout.addLayout(replay_row)

        # Timeline + 暫停/開始按鈕
        timeline_row = QHBoxLayout()
        timeline_row.addWidget(self.btn_toggle_play)
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 100)
        timeline_row.addWidget(self.timeline_slider)
        layout.addLayout(timeline_row)

        # Set layout
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def toggle_play(self):
        if self.is_playing:
            self.btn_toggle_play.setText("▶")  # 切回播放圖示
            print("⏸️ 暫停影片")
            # TODO: self.video_player.pause() （如有 pause 方法）
        else:
            self.btn_toggle_play.setText("||")  
            print("▶️ 播放影片")
            # TODO: self.video_player.play() （如有 play 方法）
        self.is_playing = not self.is_playing

    def start_recording(self): print("▶️ 開始錄影")
    def pause_recording(self): print("⏸️ 暫停錄影")
    def save_recording(self): print("💾 儲存影片")
    def run_video_processing(self): print("📦 對錄影資料夾所有影片做分析")
    def export_report(self): print("📄 匯出報告")
    def replay_existing_analysis(self): print("🎞️ 回放已分析影片")
    def video_selected(self, path): print(f"選擇影片：{path}")
