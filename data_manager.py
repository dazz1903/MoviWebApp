"""Database operations for users and their favorite movies."""

from sqlalchemy.exc import SQLAlchemyError

from models import db, User, Movie


class DataManager:
    """Manage records within an active Flask application context."""

    def rollback(self):
        """Discard pending changes after a failed database operation."""
        db.session.rollback()

    @staticmethod
    def _validate_name(name, maximum_length):
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Name must not be empty.')
        name = name.strip()
        if len(name) > maximum_length:
            raise ValueError(f'Name must not exceed {maximum_length} characters.')
        return name

    @staticmethod
    def _commit():
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise

    def create_user(self, name):
        """Save and return a new user."""
        user = User(name=self._validate_name(name, 100))
        db.session.add(user)
        self._commit()
        return user

    def get_users(self):
        """Return all users ordered by their IDs."""
        return db.session.scalars(db.select(User).order_by(User.id)).all()

    def get_user(self, user_id):
        """Return one user, or None if the user does not exist."""
        return db.session.get(User, user_id)

    def get_movie(self, movie_id, user_id):
        """Return a movie only when it belongs to the specified user."""
        return db.session.scalar(
            db.select(Movie).where(Movie.id == movie_id, Movie.user_id == user_id)
        )

    def get_movies(self, user_id):
        """Return the user's movies, or an empty list when none exist."""
        return db.session.scalars(
            db.select(Movie).where(Movie.user_id == user_id).order_by(Movie.id)
        ).all()

    def add_movie(self, movie):
        """Save and return a Movie populated by the calling code."""
        if not isinstance(movie, Movie):
            raise TypeError('Expected a Movie object.')
        name = self._validate_name(movie.name, 200)
        if movie.user_id is None or db.session.get(User, movie.user_id) is None:
            raise ValueError('Movie must belong to an existing user.')
        movie.name = name
        db.session.add(movie)
        self._commit()
        return movie

    def update_movie(self, movie_id, new_title):
        """Rename a movie and return it; reject a missing movie."""
        title = self._validate_name(new_title, 200)
        movie = db.session.get(Movie, movie_id)
        if movie is None:
            raise ValueError('Movie not found.')
        movie.name = title
        self._commit()
        return movie

    def delete_movie(self, movie_id):
        """Delete a movie; reject a missing movie."""
        movie = db.session.get(Movie, movie_id)
        if movie is None:
            raise ValueError('Movie not found.')
        db.session.delete(movie)
        self._commit()
