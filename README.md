TIGRQC is the 'Translational Imaging-Genetics Research' (TIGR) Quality Control (QC) dashboard for MRI data.

It provides an easy to use dashboard that centralizes quality control of raw MRI data and hosts quality control metrics for a variety of processing pipelines with minimal configuration required.

To install:
```bash
# if using pip. Use -e for an editable install.
pip install .

# Or if using uv. This is editable by default.
uv sync
```

To run the app:
```bash
# Run as a development instance. Do this in the root folder.
flask --app tigrqc run --debug
```
