from PyQt6.QtWidgets import QMainWindow, QLabel, QWidget, QVBoxLayout

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Paragon Apartment Management System")
        self.setMinimumSize(900, 600)

        root = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("✅ App launched successfully."))

        root.setLayout(layout)
        self.setCentralWidget(root)