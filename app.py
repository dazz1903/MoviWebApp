import os

from flask import Flask, redirect, render_template, request, url_for

from data_manager import DataManager
from models import db, Movie, User


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
def index():
    users = data_manager.get_users()
    return render_template('index.html', users=users)


@app.route('/users', methods=['POST'])
def create_user():
    try:
        data_manager.create_user(request.form.get('name', ''))
    except ValueError as error:
        return render_template(
            'index.html', users=data_manager.get_users(), error=str(error)
        ), 400
    return redirect(url_for('index'))


@app.route('/users/<int:user_id>/movies', methods=['GET'])
def get_movies(user_id):
    user = db.get_or_404(User, user_id)
    movies = data_manager.get_movies(user_id)
    return render_template('movies.html', user=user, movies=movies)


@app.route('/users')
def list_users():
    users = data_manager.get_users()
    return str(users)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run()
