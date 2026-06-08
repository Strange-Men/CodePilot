# CodePilot Product Quality Audit

> Date: 2026-06-07
> Auditor: Claude (automated)
> Scope: Report output quality across 5 representative repositories
> Mode: Mock LLM (default configuration)

## Test Repositories

| Repository | Type | Files Analyzed | Files Skipped | Coverage |
|---|---|---|---|---|
| Flask (pallets/flask) | Python web framework | 83 | 0 | 100% |
| FastAPI (fastapi/fastapi) | Python web framework | 300 | 824 | 27% |
| Click (pallets/click) | Python CLI library | 63 | 0 | 100% |
| Express (expressjs/express) | JavaScript web framework | 141 | 0 | 100% |
| Axios (axios/axios) | JavaScript HTTP client | 201 | 0 | 100% |

## Audit Questions

### 1. Does the report explain what the repository does?

**Verdict: NO.**

Repository type classification is wrong or useless in 4 of 5 cases:

| Repository | Detected Type | Actual Type |
|---|---|---|
| Flask | "Command-line application" | Web framework |
| FastAPI | "Full-stack mixed-language application" | Web framework / library |
| Click | "Command-line application" | CLI library (correct) |
| Express | "JavaScript application" | Web framework |
| Axios | "JavaScript + TypeScript application" | HTTP client library |

The `_repository_type()` heuristic checks for `/api/` or `/routes/` in paths (triggers "Web application") or `cli.` filename prefix (triggers "Command-line application"). Flask has `cli.py` so it's classified as CLI. Express has no `/api/` directory. Axios gets the generic language fallback.

### 2. Does the report identify the true entry points?

**Verdict: PARTIALLY, with significant noise.**

| Repository | True Entry Points | Detected | Accuracy |
|---|---|---|---|
| Flask | `app.py`, `__main__.py` | 6 files including `sessions.py`, `sansio/scaffold.py` | Noisy |
| FastAPI | `applications.py`, `__main__.py` | 30+ files including 20+ `docs_src` examples | Terrible |
| Click | `core.py`, `decorators.py` | `decorators.py`, `utils.py` | Partial |
| Express | `index.js`, `lib/application.js` | `lib/application.js` only | Partial |
| Axios | `index.js`, `lib/axios.js` | `sandbox/server.js` only | Wrong |

`detect_entry_point()` matches filenames (`main.py`, `app.py`, `server.py`) and scans source for framework markers (`flask(`, `fastapi(`, `express(`). This causes false positives in example directories.

### 3. Does the report identify the most important modules?

**Verdict: YES for source modules. NO because test files dominate.**

Test files appear in Top Files rankings across all repos:
- Flask: 3 of 10 are tests (test_basic.py ranked #1)
- Click: 4 of 10 are tests
- Express: 5 of 10 are tests
- Axios: 4 of 10 are tests (http.test.js ranked #1 at 6178 lines)

The -20 score modifier for test files is insufficient to prevent large test suites from dominating rankings.

### 4. Does the report correctly explain dependency hotspots?

**Verdict: PARTIALLY.**

Fan-in numbers are accurate. Hub files are correctly identified:
- Flask: `globals.py` (fan_in=12) -- correct, holds `current_app`, `request`, `g`, `session`
- FastAPI: `__init__.py` (fan_in=84) -- correct, re-exports entire public API
- Axios: `lib/utils.js` (fan_in=40) -- correct, shared utility module

**Critical flaw**: Circular dependency detection flags Python `__init__.py` re-exports as cycles. Flask's "20-file cycle" and FastAPI's "6-file cycle" are standard package re-export patterns, not actual circular dependencies.

Interpretation is always identical template text regardless of the specific file.

### 5. Does the onboarding guide help a new developer?

**Verdict: NO.**

Every onboarding entry uses one of three template explanations:
- Entry Points: "Start here to see how the application boots and connects its top-level dependencies."
- Hubs: "Read this next because many modules depend on it; its public behavior explains a large part of the repository."
- Core Modules: "Read this to understand a central domain or service boundary after startup is clear."

Problems:
- FastAPI recommends starting with `docs_src/app_testing/app_a_py310/main.py` (an example file)
- Express includes 5 test files in the 8-file reading order
- Axios starts with `sandbox/server.js` (a demo server)
- All entries for a given role have identical explanations

### 6. Does the architecture overview reflect the real architecture?

**Verdict: NO.**

The overview is a directory listing with file counts:
- Flask: "tests (41 files), src (24 files), examples (17 files), docs (1 files)"
- FastAPI: "docs_src (168 files), tests (88 files), fastapi (28 files), scripts (13 files), docs (3 files)"

No pattern identification (MVC, middleware chain, plugin system), no layer explanation, no data flow description.

### 7. Are refactoring suggestions specific or generic?

**Verdict: GENERIC. Completely generic.**

Every refactoring suggestion across all 5 reports uses one of two templates:

For overloaded files:
> "Look for cohesive groups of functions or classes that can move behind a smaller interface. The goal is to reduce independent reasons to change, not merely shorten the file."

For hub files:
> "{N} modules depend on this bottleneck. A narrow interface and contract tests can contain change impact before larger extraction work."

This text is repeated verbatim for every file in every report. Zero file-specific analysis.

### 8. Are risk hotspots useful?

**Verdict: PARTIALLY.**

Fan-in-based hotspots are genuinely useful. "Responsibility concentration" hotspots are noisy:
- Flag test files as overloaded (normal for integration test suites)
- Flag utility modules as overloaded (their job is many small functions)
- Threshold (`max(200, avg_lines * 1.75)`) is arbitrary

Missing: security hotspots, performance hotspots, error handling hotspots, API surface analysis.

### 9. Does the report contain repetitive AI-generated filler?

**Verdict: YES. Extremely.**

The mock LLM output is 100% filler. Repetition quantified for a single Flask report:
- "Start here to see how the application boots..." -- 6 times
- "Look for cohesive groups of functions..." -- 3 times
- "Interface or behavior changes here can spread widely..." -- 3 times

### 10. What percentage of the report would a senior engineer consider actionable?

**Estimated: 15-25%**

Actionable: hub file fan-in numbers, Top Files table, dependency relationships, entry point file paths.
Non-actionable: all LLM-generated sections, all refactoring suggestions, all onboarding explanations, architecture overview, type classification, circular dependency warnings, orphan lists.

## Output Quality Scorecard

| Section | Score | Notes |
|---|---|---|
| Architecture Overview | 2/10 | Wrong classifications, directory listing, no pattern explanation |
| Onboarding Guide | 3/10 | Correct file ordering, identical explanations, includes tests/examples |
| Risk Hotspots | 5/10 | Fan-in data accurate; overload detection noisy; no semantic analysis |
| Refactoring Suggestions | 1/10 | 100% generic boilerplate, identical across all files and repos |
| Repository Summary | 4/10 | Metrics accurate; type classification wrong; summary is template |
| Dependency Analysis | 7/10 | Graph data accurate; false positive cycles from re-exports |
| Overall Insight Quality | 3/10 | Structural data solid; interpretive layer adds almost no value |

## Comparison Against Alternatives

### vs. Simple Static Analysis (pylint, eslint)

CodePilot adds dependency graph, importance scoring, and cross-file relationship mapping that linters lack. But misses line-level issues, style checks, and type-aware analysis. Complementary, not competitive.

### vs. SonarQube-style Metrics

SonarQube provides quality gates, historical trending, line-level issue tracking, and CI/CD integration that CodePilot lacks. CodePilot's unique value is importance scoring and reading order generation. SonarQube is more mature and actionable.

### vs. LLM-powered Understanding (Cursor, Copilot Workspace)

LLM-powered tools provide dramatically more useful insights because they understand what the code does, not just how it's structured. CodePilot's mock mode is not competitive. Even with a real LLM, the 5000-token prompt budget and structured-context-only approach limits insight depth.

### Position

Between simple static analysis and SonarQube, with a unique but underutilized advantage in importance scoring. Not competitive with LLM-powered understanding tools.

## Top 10 Weaknesses

1. **Mock LLM output is pure filler** -- 4 LLM-generated sections add zero value.
2. **Refactoring suggestions are 100% generic** -- One of two template sentences for every file.
3. **Repository type classification is wrong** -- Flask = "Command-line application".
4. **Entry point detection is noisy** -- Filename matching causes false positives in examples.
5. **Test files pollute all rankings** -- Top Files, Hotspots, Onboarding, Refactoring all include tests.
6. **Circular dependency false positives** -- Python `__init__.py` re-exports flagged as cycles.
7. **Onboarding explanations are identical** -- Same template text for every file of the same role.
8. **No semantic understanding** -- Can't explain what a file does, only how big it is.
9. **Architecture overview is a directory listing** -- No pattern or layer identification.
10. **300-file cap causes information loss** -- FastAPI: only 27% of files analyzed.

## Top 10 Improvements for User Value

1. **Replace mock LLM with real LLM analysis** -- Use structured context as input to a real LLM.
2. **Separate test files from source code** -- Filter tests out of all analysis sections.
3. **Fix repository type classification** -- Use package metadata, README, and code patterns.
4. **Fix entry point detection** -- Exclude docs/examples directories.
5. **Make refactoring suggestions file-specific** -- Analyze actual functions/classes for splits.
6. **Fix circular dependency detection** -- Recognize `__init__.py` re-exports as non-cyclical.
7. **Differentiate onboarding explanations** -- Explain what each file does and why to read it.
8. **Add semantic file summaries** -- Use AST data to describe what files actually do.
9. **Increase token budget or use hierarchical analysis** -- Two-pass approach for large repos.
10. **Add executive summary** -- 3-5 sentence overview of what the repo does and its main risks.

## V3 Recommendation

**Primary goal**: Semantic understanding over structural metrics.

**Single most impactful feature**: Real LLM-powered report generation with the existing structured context. The structural data (dependency graph, file summaries, importance scores, hub analysis, role classification) is genuinely valuable input. The problem is the interpretive layer. A real LLM could explain what the repository does, why specific files are hubs, suggest specific refactoring moves, and detect real architecture patterns -- all using the same data CodePilot already computes.
