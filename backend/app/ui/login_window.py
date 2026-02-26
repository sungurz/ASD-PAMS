from PyQt6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout

class LoginWindow(QWidget):
    def __init__(self, on_login_success):
        super().__init__()

        self.on_login_success = on_login_success

        self.setWindowTitle("Login")
        self.setMinimumSize(300, 200)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.login_btn = QPushButton("Login")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Please log in"))
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addWidget(self.login_btn)

        self.setLayout(layout)