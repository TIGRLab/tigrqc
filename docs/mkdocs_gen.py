"""Auto-discover package contents and generate API docs from docstrings.
"""

import importlib
import os
import pkgutil
import sys
from pathlib import Path

import mkdocs_gen_files

package_root = Path(__file__).parent.parent
sys.path.insert(0, str(package_root))

# This defines which top-level packages get auto-generated API docs.
API_PACKAGES = ['tigrqc']

# This defines which modules to avoid generating API docs for.
IGNORE_MODULES = ['tigrqc.config']

# Change this to change the API section name in the built docs
# (underscores become spaces)
SECTION_NAME = 'API_Reference'

# Update this to include markdown files from outside the 'docs' dir
INCLUDED_FILES = {
    package_root / 'README.md': 'index.md',
    package_root / 'CONTRIBUTING.md': 'contributing.md',
}


def include_file(md_path: Path, dest_name: str) -> None:
    """Include a markdown file from outside the docs dir.

    Args:
        md_path (pathlib.Path): The path to a markdown file to include in
            the mkdocs outputs.
        dest_name (str): The output file name for mkdocs to use.
    """
    with open(md_path, 'r', encoding='utf-8') as fh:
        md_contents = fh.read()

    with mkdocs_gen_files.open(dest_name, 'w', encoding='utf-8') as fh:
        fh.write(md_contents)


def generate_api(
        package_name: str,
        section_name: str,
        ignore: list[str] | None = None
) -> None:
    """Generate API docs from docstrings.

    Args:
        package_name (str): The name of the top level package to generate API
            docs for.
        section_name (str): The section name for mkdocs to use. Note that
            underscores will be displayed as spaces.
        ignore (list[str], optional): An optional list of packages and modules
            to skip API documentation generation for. Useful when manual
            documentation is preferred.
    """
    if not ignore:
        ignore = []

    package = importlib.import_module(package_name)

    for _, module_name, is_pkg in pkgutil.walk_packages(
            package.__path__,
            prefix=f'{package_name}.'
    ):
        if is_pkg:
            # Only document submodules to avoid info duplication.
            continue

        if any(module_name.startswith(item) for item in ignore):
            # Skip explicitly ignored submodules
            continue

        md_path = Path(section_name) / f'{module_name.replace(".", os.sep)}.md'

        with mkdocs_gen_files.open(str(md_path), 'w') as fd:
            fd.write(f'# {module_name}\n\n')
            fd.write(f'::: {module_name}\n')

        mkdocs_gen_files.set_edit_path(str(md_path), str(md_path))


for md_file, output_name in INCLUDED_FILES.items():
    include_file(md_file, output_name)

for item in API_PACKAGES:
    generate_api(item, SECTION_NAME, ignore=IGNORE_MODULES)
