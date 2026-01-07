from flask_sqlalchemy import SQLAlchemy

# db 객체를 먼저 생성하고 app.py에서 초기화할 거야
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    user_type = db.Column(db.String(20), nullable=False)
    company_name = db.Column(db.String(100), nullable=True)
    biz_number = db.Column(db.String(20), nullable=True)