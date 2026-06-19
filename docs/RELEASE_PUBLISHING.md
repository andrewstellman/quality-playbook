# Release publishing — trusted-publisher setup + test plan (PyPI + npm via OIDC)

*Runbook for the `.github/workflows/publish.yml` CI/CD pipeline added in v1.5.10. The workflow publishes `quality-playbook` to PyPI + npm on a published GitHub Release, via OIDC trusted publishing — no stored tokens, no OTP. Do the one-time setup + test passes below BEFORE creating the first real release tag.*

*Status when written (2026-06-18): `publish.yml` Council-passed and queued to land on branch `1.5.10` (instruction 054). Both packages already exist on the registries at v1.5.8, so PyPI/npm registration is "add to existing project," not first-publish.*

---

## The one constraint that orders everything

**A GitHub Actions workflow can only run once it's on the repository's default branch (`main`) on `origin`.** `publish.yml` lands on branch `1.5.10` first; it is NOT testable or triggerable until that file reaches `origin/main`. So the order is always:

1. Get `publish.yml` onto `origin/main` (merge/push `1.5.10`, or cherry-pick the workflow to `main` early for testing).
2. Register the publishers + create the `release` environment (Step 1).
3. Run the test layers (Step 2) — these use manual dispatch and need NO tag.
4. Only then create the real release tag (Step 3). The tag is the last action.

"Test before tag" holds because the test layers run via `workflow_dispatch` on `main`, before any release tag exists.

---

## Step 1 — Register the publishers (one-time)

### PyPI (real — pypi.org)
1. Log in at pypi.org → **Your projects** → `quality-playbook` → **Manage** → **Publishing** (left sidebar).
2. Under "Add a new publisher," choose **GitHub**.
3. Fill exactly:
   - Owner: `andrewstellman`
   - Repository name: `quality-playbook`
   - Workflow name: `publish.yml`
   - Environment name: `release`
4. Click **Add**.

### TestPyPI (test.pypi.org — for the safe test pass)
Separate site, separate login. `quality-playbook` won't exist there, so use the **pending-publisher** flow (same form, registered before the project exists; the first publish creates it). Same four fields as above. This lets you rehearse the real PyPI OIDC flow against the test registry.

### npm (npmjs.com)
1. Log in → `npmjs.com/package/quality-playbook` → **Settings**.
2. Find the **Trusted Publisher** section → select **GitHub Actions**.
3. Fill:
   - Organization/user: `andrewstellman`
   - Repository: `quality-playbook`
   - Workflow filename: `publish.yml`
   - Environment: `release`
4. Save. (Must be a package owner. The workflow's `npm install -g npm@latest` satisfies npm's ≥11.5.1 requirement; provenance is automatic under trusted publishing.)

### GitHub `release` environment
Repo → **Settings → Environments → New environment** → name it **`release`** (must match the registrations exactly). Add **Required reviewers** (yourself). This reviewer gate is what makes the publish jobs *pause for approval* — the safety mechanism the test layers rely on.

---

## Step 2 — Test, in increasing risk order

### Layer 0 — local dry-run (zero registry contact)
From a clean checkout (not while the worker is mid-operation in the same repo):
```bash
python -m bin.build_channel_package --stage
python -m pip install --upgrade build && python -m build --outdir pip-dist .
# confirm the wheel contains the bundle:
python - <<'PY'
import glob, zipfile
w = glob.glob("pip-dist/*.whl")[0]
names = zipfile.ZipFile(w).namelist()
assert "quality_playbook_cli/_bundle/bin/install_skill.py" in names, "bundle missing!"
print("wheel bundle OK:", len(names), "entries")
PY
npm pack --pack-destination npm-dist
npm publish "$(ls npm-dist/*.tgz)" --access public --provenance --dry-run
```
Catches build / version-stamp / staging errors before GitHub is involved.

### Layer 1 — stage-only on real CI (no publish)
With `publish.yml` on `origin/main` and the `release` environment carrying required reviewers:
- **Actions → publish → Run workflow** (`workflow_dispatch`), give it a dummy version.
- The `stage` job runs fully: build, the four-surface version check, the wheel-content assertion, artifact upload.
- The `pypi`/`npm` jobs hit the `release` environment and **wait for approval — do NOT approve.** Nothing publishes.
- Download the artifacts and eyeball them. This validates the whole pipeline minus the final push.

### Layer 2 — TestPyPI end-to-end (proves the OIDC handshake for pip)
- Temporarily point the pypi job at TestPyPI: `with: { repository-url: https://test.pypi.org/legacy/, skip-existing: true }`.
- Dispatch, approve only the pypi job, confirm the package lands at test.pypi.org.
- Revert the override. This is the real OIDC token mint, against the test registry.

### Layer 3 — npm
npm has no clean test registry. Layers 0–1 cover packaging; the residual is npm's live OIDC mint, exercisable only by actually publishing. Two options:
- **Accept first-real-as-test:** the `skip-existing` (PyPI) + npm dup-detection net means a partial/failed run re-runs to green on the same version. Pair with the Layer-0 dry-run.
- **Belt-and-suspenders:** publish a throwaway scoped package once (`@andrewstellman/qpb-oidc-test`) with its own trusted-publisher config to rehearse the exact npm OIDC flow.

Recommended: dry-run + the idempotency net unless you want the throwaway-package rehearsal.

---

## Step 3 — Real release

1. Create the GitHub Release with tag `v1.5.10`.
2. Both publish jobs pause at the `release` environment → **approve** → they publish (PyPI + npm, npm with provenance).
3. Verify the version is live on both registries.

### Version-burn note
`skip-existing` (PyPI) + npm dup-detection mean a *partial* failure (one registry succeeded, the other errored) **re-runs to green on the same version** — no burn needed. You only burn a version number if content actually published wrong, because registries forbid overwriting an existing version. So a failed *run* is recoverable in place; a bad *publish* needs a bump.

---

## Quick reference — the four registration fields (identical everywhere)
| Field | Value |
|---|---|
| Owner / org | `andrewstellman` |
| Repository | `quality-playbook` |
| Workflow filename | `publish.yml` |
| Environment | `release` |

## Sources
- PyPI — adding a trusted publisher: https://docs.pypi.org/trusted-publishers/adding-a-publisher/
- PyPI — creating a project via OIDC (pending publishers, for TestPyPI): https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/
- npm — trusted publishing: https://docs.npmjs.com/trusted-publishers/
- GitHub Changelog — npm trusted publishing GA (2025-07-31): https://github.blog/changelog/2025-07-31-npm-trusted-publishing-with-oidc-is-generally-available/
