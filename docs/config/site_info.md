# Site Info

## Description
::: tigrqc.config.site_info
    options:
      show_root_heading: false
      members: false

## Site Personalization Settings

- `TIGRQC_DATA_DIRS`
    - **Description:** The directories to serve data from. Should be a colon
        separated list of directories that will host scan data and QC
        data. Be mindful to keep the directories as limited as possible (i.e.
        don't just give it the root directory on the server) to avoid
        unauthorized access / modification of important files. Also, for
        security reasons relative paths are completely ignored. Note that if
        the application is running behind a webserver (e.g. nginx) the
        webserver must be authorized to serve from these directories also
        or files will not be accessible to users.
    - **Default:** `None`

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
