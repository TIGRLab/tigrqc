# Authentication

## Description
::: tigrqc.config.auth
    options:
      show_root_heading: false
      members: false

## Authentication Behavior
These settings configure how the application applies user authentication.

- `TIGRQC_DISABLE_AUTH`
    * **Description:** Whether to disable user authentication for the entire app. If the application is running in debug mode and no authentication methods have been configured this flag does **not** need to be set; Authentication is disabled  automatically. This flag can allow you to disable auth for a production instance but it's probably not a good idea to do that :)
    * **Default:** `False`

## Authentication Methods
These settings turn various authentication methods on. At least one authentication method should be configured before running a production instance.