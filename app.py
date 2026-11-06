import os

from flask import Flask

from data_manager import DataManager
from models import db, Movie


app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, 'data'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(basedir, 'data/movies.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
data_manager = DataManager()


@app.route('/')
def home():
    return 'Welcome to MoviWeb App!'


@app.route('/users')
def list_users():
    users = data_manager.get_users()
    return str(users)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run()
