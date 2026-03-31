# Flask

## Description
::: tigrqc.config.flask
    options:
      show_root_heading: false
      members: false

## Flask Settings

- `FLASK_SECRET_KEY`
    * **Description:** The secret key that flask should use to protect user sessions and cookies. This should be a long, cryptographically secure, string that you keep private. If the key changes all existing user sessions and cookies will be invalidated. If one is not given, a default key will be used. This default should _only_ be used by development instances that are not exposed to anything other than localhost, because a known key or simple key is a security vulnerability.
    * **Default:** `dev-key-do-not-use-in-production!`
