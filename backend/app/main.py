import sys
from PyQt6.QtWidgets import QApplication
from sqlalchemy import text

from app.ui.main_window import MainWindow
from app.db.database import engine

def test_db_connection():
    # Simple query to verify MySQL connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

def main():
    # 1) Verify DB first (fast fail if config is wrong)
    test_db_connection()

    # 2) Start UI
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()