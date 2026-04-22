# Ahmet (24034408) 
from sqlalchemy.orm import Session
from app.db.models import User
from app.auth.security import verify_password

def authenticate_user(db,username,password):
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        return None
    if  verify_password(password, user.password_hash):
        return user
    return None 