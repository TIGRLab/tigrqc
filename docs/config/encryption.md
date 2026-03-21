# Encryption

## Description
::: tigrqc.config.encryption
    options:
      show_root_heading: false
      members: false

## Encryption Settings

### Optional Settings

- `TIGRQC_ENCRYPTION_KEY`
    * **Description:** A fernet key or the path to a file containing a fernet key. If unset, certain sensitive columns in the database will be stored in plain text.
    * **Default:** `None`
