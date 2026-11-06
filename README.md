# MoviWebApp

A Flask app for creating user profiles and managing their favorite movies.

## Run in PyCharm

Use `.venv\Scripts\python.exe` as the project interpreter. Install dependencies in the project terminal:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000. Starting `app.py` creates missing database tables automatically.

## OMDb configuration

Get your own API key from [OMDb](https://www.omdbapi.com/apikey.aspx).
In **Run → Edit Configurations**, select `app.py` and use the environment-variable editor to set:

- `OMDB_API_KEY`: your private key, used only on the server.
- `SECRET_KEY`: optional stable private value used for Flask session signing.

Restart the app after changing environment variables. The app reads the environment directly; it does not load `.env` files automatically. Never commit API keys.

## Use

Create a user on the homepage and select their name. Search by movie title to add OMDb metadata and a poster. Edit a title directly without an OMDb lookup, or delete a favorite. Movies belong to the user specified by the route; edit and delete requests reject movies belonging to another profile.

User selection is not authentication: this learning project has no passwords or private accounts.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use a temporary database and mocked OMDb requests, leaving your saved data untouched and making no API calls.
