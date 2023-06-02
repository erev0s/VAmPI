import datetime
import jwt
from sqlalchemy.orm import relationship
from config import db, vuln_app
from app import vuln, alive
from models.books_model import Book
from random import randrange
from sqlalchemy.sql import text

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), nullable=False)
    admin = db.Column(db.Boolean, nullable=False, default=False)

    books = relationship("Book", order_by=Book.id, back_populates="user")

    def __init__(self, username, password, email, admin=False):
        self.username = username
        self.email = email
        self.password = password
        self.admin = admin

    def __repr__(self):
        return f'{{"username": "{self.username}", "email": "{self.email}"}}'

    def encode_auth_token(self, user_id):
        try:
            payload = {
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=0, seconds=alive),
                'iat': datetime.datetime.utcnow(),
                'sub': user_id
            }
            return jwt.encode(
                payload,
                vuln_app.app.config.get('SECRET_KEY'),
                algorithm='HS256'
            )
        except Exception as e:
            return e

    @staticmethod
    def decode_auth_token(auth_token):
        try:
            payload = jwt.decode(auth_token, vuln_app.app.config.get('SECRET_KEY'), algorithms=["HS256"])
            return payload['sub']
        except jwt.ExpiredSignatureError:
            return 'Signature expired. Please log in again.'
        except jwt.InvalidTokenError:
            return 'Invalid token. Please log in again.'

    def json(self):
        return{'username': self.username, 'email': self.email}

    def json_debug(self):
        return{'username': self.username, 'password': self.password, 'email': self.email, 'admin': self.admin}

    @staticmethod
    def get_all_users():
        return [User.json(user) for user in User.query.all()]

    @staticmethod
    def get_all_users_debug():
        return [User.json_debug(user) for user in User.query.all()]

    @staticmethod
    def get_user(username):
        if vuln:  # SQLi Injection
            user_query = f"SELECT * FROM users WHERE username = '{username}'"
            query = db.session.execute(text(user_query))
            ret = query.fetchone()
            if ret:
                fin_query = '{"username": "%s", "email": "%s"}' % (ret[1], ret[3])
            else:
                fin_query = None
        else:
            fin_query = User.query.filter_by(username=username).first()
        return fin_query

    @staticmethod
    def register_user(username, password, email, admin=False):
        new_user = User(username=username, password=password, email=email, admin=admin)
        randomint = str(randrange(100))
        new_user.books = [Book(book_title="bookTitle" + randomint, secret_content="secret for bookTitle" + randomint)]
        db.session.add(new_user)
        db.session.commit()

    @staticmethod
    def delete_user(username):
        done = User.query.filter_by(username=username).delete()
        db.session.commit()
        return done

    @staticmethod
    def init_db_users():
        User.register_user("name1", "pass1", "mail1@mail.com", False)
        User.register_user("name2", "pass2", "mail2@mail.com", False)
        User.register_user("admin", "pass1", "admin@mail.com", True)
