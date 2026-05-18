# PyPI Publishing Guide

This project uses a GitHub Actions workflow at `.github/workflows/python-publish.yml`.

## What the workflow does

1. Checks out the repository.
2. Sets up Python 3.8.
3. Installs build tools.
4. Builds the source distribution and wheel.
5. Runs `twine check` on the generated artifacts.
6. Uploads the package to PyPI when a release is published or a `v*` tag is pushed.

## Required GitHub secret

Add this repository secret in GitHub:

- `PYPI_API_TOKEN` — a PyPI API token with permission to upload the package.

## Release flow

### Option 1: GitHub release

1. Create and push a version tag, for example:

```bash
git tag v1.3.4
git push origin v1.3.4
```

2. Publish a GitHub Release for that tag.
3. The workflow will build and upload the package.

### Option 2: Manual workflow run

You can also trigger the workflow manually from the GitHub Actions page.

## Local verification

Before publishing, you can test locally:

```bash
python -m build
python -m twine check dist/*
```

