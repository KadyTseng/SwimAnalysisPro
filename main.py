import sys
from PyQt5.QtWidgets import QApplication
from UI.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()

    window.controls.video_selected.connect(window.video_player.load_video)

    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
