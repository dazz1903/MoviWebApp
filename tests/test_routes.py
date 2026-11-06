"""Route and OMDb checks without touching the saved library or the network."""

import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app import app, data_manager, db
from models import Movie
from omdb import OMDbError, fetch_movie


class RouteTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.context = app.app_context()
        self.context.push()
        self.original = db.engines[None]
        self.temporary = create_engine('sqlite:///:memory:')
        db.engines[None] = self.temporary
        db.create_all()
        self.user = data_manager.create_user('Alice')
        self.other = data_manager.create_user('Bob')
        self.movie = data_manager.add_movie(Movie(
            name='Inception', director='Christopher Nolan', year=2010,
            user_id=self.user.id
        ))
        self.path = f'/users/{self.user.id}/movies'
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.engines[None] = self.original
        self.temporary.dispose()
        self.context.pop()

    def test_pages_and_user_creation(self):
        self.assertIn(b'Alice', self.client.get('/').data)
        self.assertIn(b'Inception', self.client.get(self.path).data)
        self.assertNotIn(b'<h3>Inception</h3>', self.client.get(f'/users/{self.other.id}/movies').data)
        response = self.client.post('/users', data={'name': 'Carol'}, follow_redirects=True)
        self.assertIn(b'Carol', response.data)
        self.assertEqual(self.client.post('/users', data={'name': ' '}).status_code, 400)
        self.assertEqual(self.client.get('/users/999/movies').status_code, 404)

    def test_custom_not_found_page(self):
        for path in ['/missing-page', '/users/999/movies']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertIn(b'404', response.data)
                self.assertIn(b'Return to the user list', response.data)

    def test_database_read_failure_and_recovery(self):
        with patch('app.data_manager.get_users', side_effect=SQLAlchemyError('private SQL data')):
            with patch('app.data_manager.rollback', wraps=data_manager.rollback) as rollback:
                with self.assertLogs(app.logger, level='ERROR') as logs:
                    response = self.client.get('/')
                rollback.assert_called_once_with()
                self.assertNotIn('private SQL data', '\n'.join(logs.output))
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Something went wrong', response.data)
        self.assertNotIn(b'private SQL data', response.data)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_failed_write_is_rolled_back(self):
        with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('write failure')):
            with self.assertLogs(app.logger, level='ERROR'):
                response = self.client.post('/users', data={'name': 'Unsaved user'})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('Unsaved user', [user.name for user in data_manager.get_users()])
        self.assertEqual(self.client.post('/users', data={'name': 'Saved user'}).status_code, 302)

    def test_unexpected_exception_uses_custom_server_page(self):
        # Match Flask's normal non-debug behavior rather than propagating test exceptions.
        with patch.dict(app.config, {'PROPAGATE_EXCEPTIONS': False}):
            with patch('app.data_manager.get_users', side_effect=RuntimeError('private details')):
                with self.assertLogs(app.logger, level='ERROR'):
                    response = self.client.get('/')
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Something went wrong', response.data)
        self.assertNotIn(b'private details', response.data)

    @patch('app.fetch_movie')
    def test_add_movie_and_redirect(self, lookup):
        lookup.return_value = {'name': 'Alien', 'director': 'Ridley Scott',
                               'year': 1979, 'poster_url': 'https://example.com/alien.jpg'}
        response = self.client.post(self.path, data={'title': ' Alien '})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], self.path)
        lookup.assert_called_once_with('Alien')
        saved = data_manager.get_movies(self.user.id)[-1]
        self.assertEqual((saved.name, saved.year, saved.user_id), ('Alien', 1979, self.user.id))
        self.assertIn(b'example.com/alien.jpg', self.client.get(self.path).data)

    @patch('app.fetch_movie', side_effect=OMDbError('Movie not found.', 404))
    def test_failed_lookup_changes_no_data(self, lookup):
        response = self.client.post(self.path, data={'title': 'Unknown'})
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'Movie not found.', response.data)
        self.assertEqual(len(data_manager.get_movies(self.user.id)), 1)

    @patch.dict(os.environ, {'OMDB_API_KEY': ''})
    def test_missing_api_key(self):
        response = self.client.post(self.path, data={'title': 'Alien'})
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'OMDB_API_KEY', response.data)

    @patch('app.fetch_movie')
    def test_update_is_local_and_validates_title(self, lookup):
        path = f'{self.path}/{self.movie.id}/update'
        response = self.client.post(path, data={'new_title': ' New title '}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.movie.name, 'New title')
        self.assertEqual((self.movie.director, self.movie.year), ('Christopher Nolan', 2010))
        lookup.assert_not_called()
        self.assertEqual(self.client.post(path, data={'new_title': ''}).status_code, 400)
        self.assertEqual(self.movie.name, 'New title')
        self.assertEqual(self.client.get(path).status_code, 405)

    def test_ownership_and_missing_movie(self):
        for action in ['update', 'delete']:
            path = f'/users/{self.other.id}/movies/{self.movie.id}/{action}'
            self.assertEqual(self.client.post(path, data={'new_title': 'Changed'}).status_code, 404)
            self.assertEqual(self.client.post(f'{self.path}/999/{action}').status_code, 404)
        self.assertEqual(self.movie.name, 'Inception')
        self.assertIsNotNone(data_manager.get_movie(self.movie.id, self.user.id))

    def test_delete_and_post_only(self):
        movie_id = self.movie.id
        path = f'{self.path}/{movie_id}/delete'
        self.assertEqual(self.client.get(path).status_code, 405)
        response = self.client.post(path, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Movie deleted successfully!', response.data)
        self.assertIsNone(data_manager.get_movie(movie_id, self.user.id))


class OMDbTests(unittest.TestCase):
    @patch.dict(os.environ, {'OMDB_API_KEY': 'test-placeholder'})
    @patch('omdb.urlopen')
    def test_normalization_and_request(self, opener):
        payload = {'Response': 'True', 'Title': 'Alien', 'Year': '1979',
                   'Director': 'Ridley Scott', 'Poster': 'https://example.com/a.jpg'}
        opener.return_value = io.BytesIO(json.dumps(payload).encode())
        result = fetch_movie('Alien & friends')
        self.assertEqual(result['year'], 1979)
        self.assertEqual(result['director'], 'Ridley Scott')
        url = opener.call_args.args[0]
        self.assertTrue(url.startswith('https://www.omdbapi.com/'))
        self.assertIn('t=Alien+%26+friends', url)
        self.assertEqual(opener.call_args.kwargs['timeout'], 10)
        payload.update(Year='N/A', Director='N/A', Poster='javascript:alert(1)')
        opener.return_value = io.BytesIO(json.dumps(payload).encode())
        result = fetch_movie('Alien')
        self.assertIsNone(result['year'])
        self.assertIsNone(result['poster_url'])
        self.assertIsNone(result['director'])

    @patch.dict(os.environ, {'OMDB_API_KEY': 'test-placeholder'})
    @patch('omdb.urlopen')
    def test_api_failures(self, opener):
        for payload in [{'Response': 'False', 'Error': 'Movie not found!'},
                        {'Response': 'False', 'Error': 'Invalid API key!'},
                        [], {'Response': 'True'}, {'Response': 'garbage'}]:
            with self.subTest(payload=payload):
                opener.return_value = io.BytesIO(json.dumps(payload).encode())
                with self.assertRaises(OMDbError):
                    fetch_movie('Alien')
        opener.side_effect = URLError('private-url?apikey=secret')
        with self.assertRaises(OMDbError) as error:
            fetch_movie('Alien')
        self.assertNotIn('secret', str(error.exception))


if __name__ == '__main__':
    unittest.main()
