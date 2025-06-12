from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout

class VideoPlayerWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label = QLabel("🎬 Video preview area")
        self.label.setStyleSheet("background-color: #222; color: #fff; padding: 20px;")
        self.label.setMinimumHeight(300)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def load_video(self, path):
        self.label.setText(f"Loaded video: {path}")
