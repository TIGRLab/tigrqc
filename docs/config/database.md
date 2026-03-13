# Database

## Description
::: tigrqc.config.database
    options:
      show_root_toc_entry: false
      show_root_heading: false
      members: false

## Database Connection Settings

### Optional Settings

- `TIGRQC_DB_NAME`
    * **Description:** The name of the database to use when a PostgreSQL database is being used.
    * **Default:** `tigrqc`

- `TIGRQC_DB_PASS`
    * **Description:** The password to connect with when a PostgreSQL database is being used. If passwordless-auth is configured it can be omitted.
    * **Default:** `None`

- `TIGRQC_DB_PATH`
    * **Description:** The path for the SQLite database if a persistent SQLite database is desired instead of an in-memory one. If any PostgreSQL-related settings (or the full database URI) are given then this will be ignored.
    * **Accepted values:** A relative or fully qualified path.
    * **Default:** `None`

- `TIGRQC_DB_PORT`
    * **Description:** The port to connect to when a PostgreSQL database is being used.
    * **Accepted values:** int
    * **Default:** `None`

- `TIGRQC_DB_POSTGRES`
    * **Description:** Indicates whether to use PostgreSQL instead of SQLite. If any other PostgreSQL-related settings are provided it's not necessary to set this. This is solely a shortcut for when postgres is desired but the default connection settings are to be used.
    * **Accepted values:** boolean
    * **Default:** `False`

- `TIGRQC_DB_SRVR`
    * **Description:** The hostname to connect to when a PostgreSQL database is being used. If unset, will try to connect to a unix socket on localhost.
    * **Default:** `None`

- `TIGRQC_DB_URI`
    * **Description:** The database connection string to use. The input will not be validated or modified in any way. Overrides all other database settings when given. This can be used to choose an untested database type at the user's own risk or to provide more complex connection settings.
    * **Default:** `None`

- `TIGRQC_DB_USER`
    * **Description:** The user to connect as when a PostgreSQL database is being used. If unset will attempt to connect as the current user.
    * **Default:** `None`

### Examples
```bash
# Switch to a persistent SQLite database
export TIGRQC_DB_PATH=/tmp/mydatabase.db

# Switch to PostgreSQL, but with the default connection settings
export TIGRQC_DB_POSTGRES=true

# Use PostgreSQL as user 'myuser'
export TIGRQC_DB_USER='myuser'

# Use a different database entirely, in this case 'mysql' (Use at your own risk)
export TIGRQC_DB_URI=`mysql://user:password@myserver/mydb`
```
