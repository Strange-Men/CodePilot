# Tag Audit — 2026-06-18

## Purpose

Audit CodePilot's Git tag history for resume/demo credibility.
Goal: every stable milestone version has a clean, lowercase, annotated tag on the remote.

## Tags Created in This Audit

| Tag | Commit | Type | Message |
|---|---|---|---|
| `v2.4` | `96527db` | annotated | `CodePilot v2.4` |
| `v2.5` | `f03cbb4` | annotated | `CodePilot v2.5` |
| `v2.6` | `e1d16f2` | annotated | `CodePilot v2.6` |
| `v3.0` | `be7e158` | annotated | `CodePilot v3.0` |
| `v3.0.1` | `b1df52e` | annotated | `CodePilot v3.0.1` (pre-existing locally, pushed) |
| `v3.5.12` | `3a21877` | annotated | `CodePilot v3.5.12 — product usability and Chinese quality fixes` |
| `v3.6` | `7464450` | annotated | `CodePilot v3.6 — UI/UX product polish` |

## Tags Intentionally NOT Pushed

| Tag | Reason |
|---|---|
| `V2.2-complete` | Inconsistent naming (uppercase prefix, `-complete` suffix). Local-only historical marker. |
| `V2.3-complete` | Inconsistent naming (uppercase prefix, `-complete` suffix). Local-only historical marker. |

## Tags Skipped (Not Created)

| Version | Reason |
|---|---|
| `v3.1` | No explicit completion/release commit marker. MEDIUM confidence — skipped per rules. |

## Remote Tag List (Final)

| Tag | Commit | Type | GitHub Release |
|---|---|---|---|
| `v1.0.0` | `627dba4` | annotated | ❌ |
| `v1.1.0` | `77a49fb` | lightweight | ❌ |
| `v1.2.0` | `ce0c80f` | annotated | ❌ |
| `v1.4.0` | `6637a70` | annotated | ❌ |
| `v2.1.0` | `871f6b6` | annotated | ❌ |
| `v2.4` | `96527db` | annotated | ❌ |
| `v2.5` | `f03cbb4` | annotated | ❌ |
| `v2.6` | `e1d16f2` | annotated | ❌ |
| `v3.0` | `be7e158` | annotated | ❌ |
| `v3.0.1` | `b1df52e` | lightweight | ❌ |
| `v3.5.9` | `0970845` | annotated | ✅ |
| `v3.5.10` | `85085ee` | annotated | ✅ |
| `v3.5.11` | `04d6ff4` | annotated | ✅ |
| `v3.5.12` | `3a21877` | annotated | ❌ |
| `v3.6` | `7464450` | annotated | ❌ |
| `v3.7` | `97322bb` | annotated | ✅ |

## Commands Run

```bash
git fetch origin --tags --prune

# Created annotated tags
git tag -a v2.4 96527db -m "CodePilot v2.4"
git tag -a v2.5 f03cbb4 -m "CodePilot v2.5"
git tag -a v2.6 e1d16f2 -m "CodePilot v2.6"
git tag -a v3.0 be7e158 -m "CodePilot v3.0"
git tag -a v3.5.12 3a21877 -m "CodePilot v3.5.12 — product usability and Chinese quality fixes"
git tag -a v3.6 7464450 -m "CodePilot v3.6 — UI/UX product polish"

# Pushed individually
git push origin v2.4
git push origin v2.5
git push origin v2.6
git push origin v3.0
git push origin refs/tags/v3.0.1    # explicit ref due to branch/tag name collision
git push origin v3.5.12
git push origin v3.6
```

## GitHub Release Cleanup

- `v3.7`, `v3.5.11`, `v3.5.10`, `v3.5.9` have GitHub Releases. ✅
- No GitHub Releases exist for historical tags (`v1.0.0` through `v3.6`). These are optional and not created unless requested.

## Verification

No existing tags were moved. No force push. No `--tags` bulk push. No source code changed.
