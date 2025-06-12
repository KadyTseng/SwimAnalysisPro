from PyQt5.QtWidgets import QWidget, QTabWidget, QTextEdit, QVBoxLayout

class AnalysisDisplayWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.summary = QTextEdit("Analysis not yet performed")
        self.kick = QTextEdit("Kick angle data")
        self.stroke = QTextEdit("Stroke statistics data")

        self.tabs.addTab(self.summary, "Segment Analysis")
        self.tabs.addTab(self.kick, "Kick Angle")
        self.tabs.addTab(self.stroke, "Stroke Analysis")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def update_analysis(self, dummy_data: str):
        self.summary.setText(dummy_data)

