from config import db
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey


class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    book_title = db.Column(db.String(128), unique=True, nullable=False)
    secret_content = db.Column(db.String(128), nullable=False)

    user_id = db.Column(db.Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="books")

    def __init__(self, book_title, secret_content, user_id=user_id):
        self.book_title = book_title
        self.secret_content = secret_content
        self.user_id = user_id

    def __repr__(self):
        return f"<User(book_title={self.book_title}, user={self.user})>"

    def json(self):
        return {'book_title': self.book_title, 'user': self.user.username}

    @staticmethod
    def get_all_books():
        return [Book.json(user) for user in Book.query.all()]
