# Site Info

## Description
::: tigrqc.config.site_info
    options:
      show_root_heading: false
      members: false

## Site Personalization Settings

- `TIGRQC_BRAND`
    - **Description:** The 'brand' to use on the site's top navbar.
    - **Default:** `TIGRQC`

- `TIGRQC_LOGO`
    - **Description:** The name of the file in the static folder to use as the site's logo.
    - **Default:** `logo.png`

- `TIGRQC_SUPPORT_EMAIL`
    - **Description:** The email users should contact with support requests. If omitted any 'Contact Support' type links will be disappear from the UI.
    - **Default:** `None`

- `TIGRQC_HELP_DOCS`
    - **Description:** The URL to provide users looking for help documentation. If not provided, tigrqc's home page will be used. This may not be ideal, since this documentation is intended more for developers than end users.
    - **Default:** tigrqc's home page (or '/' in the event that tigrqc's home page cannot be found).
