from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.ui.login_window import LoginWindow
from app.db.database import SessionLocal
from app.auth.login_service import authenticate_user

def main():
    app = QApplication([])

    db = SessionLocal()

    def handle_login():
        username = login_window.username.text()
        password = login_window.password.text()

        user = authenticate_user(db, username, password)

        if user:
            login_window.close()
            main_window = MainWindow(user.role)
            main_window.show()
        else:
            print("Login failed")

    login_window = LoginWindow(on_login_success=handle_login)
    login_window.login_btn.clicked.connect(handle_login)

    login_window.show()
    app.exec()


if __name__ == "__main__":
    main()