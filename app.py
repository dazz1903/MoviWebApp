import os

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from data_manager import DataManager
from models import db, Movie
from omdb import OMDbError, fetch_movie


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32)

basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, 'data'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(basedir, 'data/movies.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
data_manager = DataManager()


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(SQLAlchemyError)
def database_error(error):
    data_manager.rollback()
    app.logger.error('Database operation failed (%s).', type(error).__name__)
    return render_template('500.html'), 500


@app.errorhandler(500)
def internal_server_error(error):
    data_manager.rollback()
    return render_template('500.html'), 500


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
    flash('User created successfully!')
    return redirect(url_for('index'))


def require_user(user_id):
    user = data_manager.get_user(user_id)
    if user is None:
        abort(404)
    return user


def require_movie(user_id, movie_id):
    require_user(user_id)
    movie = data_manager.get_movie(movie_id, user_id)
    if movie is None:
        abort(404)
    return movie


@app.route('/users/<int:user_id>/movies', methods=['GET'])
def get_movies(user_id):
    user = require_user(user_id)
    movies = data_manager.get_movies(user_id)
    return render_template('movies.html', user=user, movies=movies)


@app.route('/users/<int:user_id>/movies', methods=['POST'])
def add_movie(user_id):
    user = require_user(user_id)
    title = request.form.get('title', '').strip()
    try:
        details = fetch_movie(title)
        data_manager.add_movie(Movie(user_id=user_id, **details))
    except (OMDbError, ValueError) as error:
        return render_template(
            'movies.html', user=user, movies=data_manager.get_movies(user_id),
            error=str(error)
        ), error.status_code if isinstance(error, OMDbError) else 400
    flash('Movie added successfully!')
    return redirect(url_for('get_movies', user_id=user_id))


@app.route('/users/<int:user_id>/movies/<int:movie_id>/update', methods=['POST'])
def update_movie(user_id, movie_id):
    require_movie(user_id, movie_id)
    try:
        data_manager.update_movie(movie_id, request.form.get('new_title', ''))
    except ValueError as error:
        return render_template(
            'movies.html', user=require_user(user_id),
            movies=data_manager.get_movies(user_id), error=str(error)
        ), 400
    flash('Movie title updated successfully!')
    return redirect(url_for('get_movies', user_id=user_id))


@app.route('/users/<int:user_id>/movies/<int:movie_id>/delete', methods=['POST'])
def delete_movie(user_id, movie_id):
    require_movie(user_id, movie_id)
    data_manager.delete_movie(movie_id)
    flash('Movie deleted successfully!')
    return redirect(url_for('get_movies', user_id=user_id))


@app.route('/users')
def list_users():
    users = data_manager.get_users()
    return str(users)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run()
