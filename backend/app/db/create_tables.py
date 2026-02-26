from app.db.database import engine, Base
from app import models
def create_tables():
    print('creating tables if they do not exist...')
    Base.metadata.create_all(bind=engine)
    print('Done')
if __name__ == "__main__":
    create_tables()