# Releasing

Releases are made by pushing a git tag. The workflow
`.github/workflows/release.yml` then runs the checks, builds the package,
publishes it to [PyPI](https://pypi.org/project/pymeinverein/) and creates a
GitHub release with generated notes.

The version is not written down anywhere: `hatch-vcs` derives it from the tag
(`v0.2.0` becomes version `0.2.0`).

## One-time setup

1. **GitHub repository.** Create it and push the code:

    ```console
    git remote add origin git@github.com:<owner>/pymeinverein.git
    git push -u origin main
    ```

2. **PyPI trusted publisher.** On PyPI open *Your account → Publishing* and add
   a pending publisher (this works before the project exists):

    | Field | Value |
    | --- | --- |
    | PyPI project name | `pymeinverein` |
    | Owner | your GitHub user or organisation |
    | Repository name | `pymeinverein` |
    | Workflow name | `release.yml` |
    | Environment name | `pypi` |

    No API token or repository secret is needed; the workflow authenticates
    through OpenID Connect.

3. **GitHub environment.** In the repository settings create an environment
   named `pypi`. Adding yourself as required reviewer there means every upload
   to PyPI waits for your approval.

4. **Project links.** Add the repository URL to `pyproject.toml` so PyPI shows
   it:

    ```toml
    [project.urls]
    Repository = "https://github.com/<owner>/pymeinverein"
    Documentation = "https://github.com/<owner>/pymeinverein/tree/main/docs"
    Changelog = "https://github.com/<owner>/pymeinverein/blob/main/CHANGELOG.md"
    ```

## Making a release

1. Make sure `main` is green in CI.
2. In `CHANGELOG.md` rename *Unreleased* to the new version and date, and start
   a new empty *Unreleased* section. Commit.
3. Tag and push:

    ```console
    git tag -a v0.2.0 -m "pymeinverein 0.2.0"
    git push origin main v0.2.0
    ```

4. Watch the *Release* workflow. It fails before publishing if the built
   version does not match the tag.

## Version numbers

The project follows [Semantic Versioning](https://semver.org/). While the
version is below 1.0, minor releases may change the Python API. Because the
library depends on an undocumented web API, a release can also become
necessary simply because the service changed.

## Trying a build locally

```console
uv build
uvx twine check dist/*
```

Between tags the version looks like `0.2.1.dev3+g1a2b3c4`; such builds are for
testing only.
