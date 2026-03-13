"""Configuration for the database and database connection.

If no database settings are provided an in memory sqlite database will
be used (i.e. it's assumed to be a dev or test instance). A path may be
provided for sqlite if persistence is needed.

If a user, password, server, port, or database name are provided it's assumed
the database will be postgresql. To enable postgresql without changing any
defaults set 'TIGRQC_DB_POSTGRES=True'

Users can choose another database at their own risk, or toggle additional
connection values, by specifying the entire database connection string.
"""
import os

from sqlalchemy.engine import URL, make_url

from tigrqc.exceptions import ConfigException

from .utils import read_boolean


def make_database_uri() -> URL:
    """Create the URI for the database based on user configuration.
    """
    # Allow advanced users to set the database URI directly.
    # Note that this allows untested databases at the user's own risk.
    db_uri = os.environ.get('TIGRQC_DB_URI', '')

    if db_uri:
        return make_url(db_uri)

    # User to connect to database as. If None, will connect as current user.
    user = os.environ.get('TIGRQC_DB_USER')

    # Password to use to connect. If unset, passwordless auth must be enabled
    password = os.environ.get('TIGRQC_DB_PASS')

    # Server to connect to. If unset, will try to connect to localhost
    server = os.environ.get('TIGRQC_DB_SRVR')

    # Name of the database to connect to. If unset, will try to use 'tigrqc'
    db_name = os.environ.get('TIGRQC_DB_NAME')

    # Port to use to connect. If unset, will use the default port
    str_port = os.environ.get('TIGRQC_DB_PORT')

    if str_port:
        try:
            port = int(str_port)
        except ValueError as e:
            raise ConfigException(
                f'int port number expected, received {str_port}'
            ) from e
    else:
        port = None

    # Enable postgres without changing defaults. Default False.
    use_postgres = read_boolean('TIGRQC_DB_POSTGRES')

    if use_postgres or any([user, password, server, db_name, port]):
        if not db_name:
            db_name = 'tigrqc'

        return URL.create(
            'postgresql',
            username=user,
            password=password,
            host=server,
            database=db_name,
            port=port
        )

    # Path for the sqlite database, if used. Defaults to in-memory database.
    sqlite_path = os.environ.get('TIGRQC_DB_PATH', ':memory:')
    return make_url(f'sqlite:///{sqlite_path}')


SQLALCHEMY_DATABASE_URI = make_database_uri()
