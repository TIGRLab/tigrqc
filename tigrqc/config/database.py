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

from .utils import read_boolean

# Allow advanced users to set the database URI directly.
# Note that this allows users to choose untested databases at their own risk.
db_uri = os.environ.get('TIGRQC_DB_URI', '')

# Path for the sqlite database, if used. Defaults to in-memory database.
sqlite_path = os.environ.get('TIGRQC_DB_PATH', ':memory:')

# User to connect to database as. If None, will connect as current user.
user = os.environ.get('TIGRQC_DB_USER')

# Password to use to connect. If unset, passwordless auth must be enabled
password = os.environ.get('TIGRQC_DB_PASS', '')

# Server to connect to. If unset, will try to connect to localhost
server = os.environ.get('TIGRQC_DB_SRVR', '')

# Name of the database to connect to. If unset, will try to use 'tigrqc'
db_name = os.environ.get('TIGRQC_DB_NAME', '')

# Port to use to connect. If unset, will use the default postgres port (5432)
port = os.environ.get('TIGRQC_DB_PORT', '')

# Enable postgres without changing defaults. Default False.
use_postgres = read_boolean('TIGRQC_DB_POSTGRES')

if db_uri:
    SQLALCHEMY_DATABASE_URI = db_uri
elif use_postgres or any([user, password, server, db_name, port]):
    if not server:
        server = 'localhost'

    if not db_name:
        db_name = 'tigrqc'

    if port:
        port = ':' + port

    SQLALCHEMY_DATABASE_URI = (
        f'postgresql://{user}:{password}@{server}{port}/{db_name}'
    )
else:
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{sqlite_path}'
