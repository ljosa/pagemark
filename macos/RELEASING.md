# Intel macOS releases

`tools/release.py` produces local release assets. It does not create or push Git
tags, upload to GitHub, or publish a release. Use a normal logged-in Intel Mac
session: the signed editor probe needs WindowServer, and the runtime probe must
run outside an additional process sandbox.

## Version and source

`macos/pyproject.toml` owns the app version and `[tool.pagemark].build-number`.
Increment both for each release. Add reviewed notes under `macos/releases/`.
The builder uses these values for Info.plist and its provenance manifest.

Commit the changes and work from a clean checkout. The release command rejects
tracked changes and untracked files, a missing tag, or a tag pointing elsewhere.
Ignored `.venv`, `.build`, and `dist` directories are allowed. Do not clean away
unrelated work to satisfy this requirement; use a separate checkout instead.

Example, after reviewing and committing version 0.2.15:

```sh
git tag -a macos-v0.2.15 -m 'Pagemark 0.2.15 for Intel Mac'
```

Use framework CPython 3.12 and the exact runtime dependencies listed in
`macos/pyproject.toml`, plus pytest and Ruff. The existing project `.venv` on
this Mac provides this environment; another checkout can use its absolute
interpreter path. No packages are installed by the release command.

## Preview build

From the repository root:

```sh
.venv/bin/python macos/tools/release.py \
  --tag macos-v0.2.15 --notes macos/releases/0.2.15.md --preview --check
.venv/bin/python macos/tools/release.py \
  --tag macos-v0.2.15 --notes macos/releases/0.2.15.md --preview
```

Preview is an explicit opt-in: it uses ad-hoc signatures without notarization
or hardened runtime, and the artifact filename and notes say so. Gatekeeper
may block it on another Mac. The App Sandbox remains enabled.

## Signed, notarized build

Install a Developer ID Application certificate and its private key in Keychain.
Configure a notarytool profile once; keep passwords and certificates out of Git:

```sh
xcrun notarytool store-credentials pagemark-notary \
  --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID
```

The tool prompts for the app-specific password. Then build:

```sh
.venv/bin/python macos/tools/release.py \
  --tag macos-v0.2.15 --notes macos/releases/0.2.15.md \
  --identity 'Developer ID Application: YOUR_NAME (YOUR_TEAM_ID)' \
  --notary-profile pagemark-notary
```

This path requires real Developer ID signing and hardened runtime, submits the
archive with `notarytool`, requires Accepted status, staples and validates the
ticket, and checks Gatekeeper. A rejected or timed-out notarization stops the
release. Diagnostics retain the submission ID; inspect an existing submission
with `xcrun notarytool info ID --keychain-profile pagemark-notary` before retrying.

Both paths run macOS and shared-core tests, Ruff, a bundle/sandbox audit, and
both signed runtime/editor probes. Every bundled Mach-O file is thinned to
x86_64 and audited. The final ZIP is unpacked and audited again to check its
signatures, symlinks, dependencies, architecture, and provenance after transport.

## Outputs and GitHub

Successful artifacts appear under:

- `macos/dist/releases/macos-v0.2.15-preview/`, or
- `macos/dist/releases/macos-v0.2.15-notarized/`.

Each contains the versioned ZIP, `SHA256SUMS`, `RELEASE_NOTES.md`, and
`release.json` (commit, build number, signing status, dependency hashes, audit).
Existing release directories are never overwritten. Failed builds retain logs
under `macos/.build/release-*` and do not create a successful artifact directory.
Builds also replace `macos/dist/Pagemark.app` in that checkout.

Review the artifacts and verify checksums before uploading:

```sh
cd macos/dist/releases/macos-v0.2.15-preview
shasum -a 256 -c SHA256SUMS
```

Push the reviewed tag, then create a draft prerelease from that directory:

```sh
git push origin macos-v0.2.15
gh release create macos-v0.2.15 \
  Pagemark-0.2.15-macOS-x86_64-preview.zip SHA256SUMS release.json RELEASE_NOTES.md \
  --repo ljosa/pagemark --verify-tag --draft --prerelease \
  --title 'Pagemark 0.2.15 — Intel Mac preview' --notes-file RELEASE_NOTES.md
```

For the notarized build, use its artifact directory and ZIP filename without
`-preview`. Keep the draft until the download has been tested on another Mac.
Publishing is a separate action in the GitHub UI. GitHub's automatically
attached source archives are not the downloadable application.

References: [Apple notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
[GitHub release command](https://cli.github.com/manual/gh_release_create).
