"""Auto-detect toolchains and extras from marker files in a project root."""

from __future__ import annotations

from pathlib import Path


# Toolchain → list of marker filenames (exact match in project root).
# Lockfiles for one ecosystem (pnpm-lock.yaml etc.) imply that ecosystem's
# toolchain (node), but the package-manager extra is detected separately.
_TOOLCHAIN_MARKERS: dict[str, tuple[str, ...]] = {
    "node": (
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lock",
        "bun.lockb",
    ),
    "python": (
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "uv.lock",
    ),
    "go": ("go.mod",),
    "rust": ("Cargo.toml",),
    "ruby": ("Gemfile",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "deno": ("deno.json", "deno.jsonc"),
    "elixir": ("mix.exs",),
    "zig": ("build.zig", "build.zig.zon"),
    "dotnet": (
        "nuget.config",
        "NuGet.Config",
        "global.json",
        "Directory.Build.props",
        "Directory.Packages.props",
    ),
    "php": ("composer.json",),
}

# Toolchain → list of glob patterns (used when the marker filename varies).
_TOOLCHAIN_GLOBS: dict[str, tuple[str, ...]] = {
    "ruby": ("*.gemspec",),
    "dotnet": ("*.csproj", "*.fsproj", "*.vbproj", "*.sln"),
}


def detect_toolchains(root: Path) -> set[str]:
    """Return the set of toolchain names whose markers exist in ``root``.

    Only the project root is inspected (no recursion) — that's where
    ecosystem manifests conventionally live and it keeps detection fast
    and predictable.
    """
    found: set[str] = set()
    for tc, markers in _TOOLCHAIN_MARKERS.items():
        if any((root / m).exists() for m in markers):
            found.add(tc)
    for tc, patterns in _TOOLCHAIN_GLOBS.items():
        if any(any(root.glob(p)) for p in patterns):
            found.add(tc)
    return found


def detect_extras(root: Path) -> set[str]:
    """Return the set of extras whose markers exist in ``root``."""
    found: set[str] = set()

    if (root / "pnpm-lock.yaml").exists():
        found.add("pnpm")
    if (root / "yarn.lock").exists():
        found.add("yarn")
    if (root / "bun.lock").exists() or (root / "bun.lockb").exists():
        found.add("bun")

    if (root / "uv.lock").exists():
        found.add("uv")
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text()
        except OSError:
            text = ""
        if "[tool.uv]" in text or "[tool.uv." in text:
            found.add("uv")

    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            text = pkg_json.read_text()
        except OSError:
            text = ""
        if (
            '"playwright"' in text
            or '"puppeteer"' in text
            or '"@playwright/test"' in text
        ):
            found.add("browser")

    compose_files = [
        root / "docker-compose.yml",
        root / "docker-compose.yaml",
        root / "compose.yml",
        root / "compose.yaml",
    ]
    has_compose = any(p.exists() for p in compose_files)
    if (root / "Dockerfile").exists() or has_compose:
        found.add("docker")

    for compose in compose_files:
        if not compose.exists():
            continue
        try:
            text = compose.read_text().lower()
        except OSError:
            continue
        if "postgres" in text:
            found.add("postgres")
        if "redis" in text:
            found.add("redis")

    if _detect_cloud(root):
        found.add("cloud")

    if _detect_liquibase(root):
        found.add("liquibase")

    return found


# Specific filenames at the root that signal IaC/Kubernetes use.
_CLOUD_ROOT_FILES: tuple[str, ...] = (
    "Chart.yaml",
    "helmfile.yaml",
    "helmfile.yml",
    "kubeconfig",
    "kustomization.yaml",
    "kustomization.yml",
)

# Glob patterns at the root that signal Terraform.
_CLOUD_ROOT_GLOBS: tuple[str, ...] = ("*.tf", "*.tfvars")

# Common directory names where Terraform / Kubernetes manifests live nested
# under the repo root. The directory existing is enough — we don't recurse
# arbitrarily, which keeps detection cheap and avoids false positives from
# matches inside node_modules / vendor / etc.
_CLOUD_DIRS: tuple[str, ...] = (
    "terraform",
    "infra",
    "iac",
    "k8s",
    "kubernetes",
    "manifests",
)


def _detect_cloud(root: Path) -> bool:
    for name in _CLOUD_ROOT_FILES:
        if (root / name).exists():
            return True
    for pattern in _CLOUD_ROOT_GLOBS:
        if any(root.glob(pattern)):
            return True
    for d in _CLOUD_DIRS:
        if (root / d).is_dir():
            return True
    return False


# ── Liquibase detection ──────────────────────────────────────────────────────
# Liquibase config and changelog filenames. The root-level files
# (`liquibase.properties`, `liquibase.flowfile.yaml`, etc.) are unambiguous,
# while changelog files are commonly placed under a `sql/`, `db/`, `db/changelog/`,
# `liquibase/`, or `migrations/` subdirectory — we look there too without
# recursing further to keep detection fast and predictable.
_LIQUIBASE_ROOT_FILES: tuple[str, ...] = (
    "liquibase.properties",
    "liquibase.flowfile.yaml",
    "liquibase.flowfile.yml",
    "liquibase.docker-compose.yaml",
    "liquibase.docker-compose.yml",
)

_LIQUIBASE_CHANGELOG_NAMES: tuple[str, ...] = (
    "db.changelog-master.yaml",
    "db.changelog-master.yml",
    "db.changelog-master.xml",
    "db.changelog-master.json",
    "db.changelog-master.sql",
    "changelog-master.yaml",
    "changelog-master.yml",
    "changelog-master.xml",
)

# Subdirectories commonly used to hold the changelog tree.
_LIQUIBASE_SUBDIRS: tuple[str, ...] = (
    "sql",
    "db",
    "db/changelog",
    "liquibase",
    "migrations",
    "changelog",
)


def _detect_liquibase(root: Path) -> bool:
    # Root-level config / flowfile filenames are unambiguous.
    for name in _LIQUIBASE_ROOT_FILES:
        if (root / name).exists():
            return True
    # Changelog file at the root.
    for name in _LIQUIBASE_CHANGELOG_NAMES:
        if (root / name).exists():
            return True
    # Or in a conventional subdirectory.
    for sub in _LIQUIBASE_SUBDIRS:
        d = root / sub
        if not d.is_dir():
            continue
        for name in _LIQUIBASE_CHANGELOG_NAMES:
            if (d / name).exists():
                return True
    return False


# ── Version pin detection ────────────────────────────────────────────────────

# asdf/mise plugin name → our --versions key. Only tools that appear in
# DEFAULT_VERSIONS are pinnable; anything else (nodejs, python, ruby, ...)
# is silently ignored because the target VM ships those pre-installed.
_TOOL_VERSIONS_ALIASES: dict[str, str] = {
    "golang": "go",
    "go": "go",
    "zig": "zig",
    "terraform": "terraform",
    "kubectl": "kubectl",
}


def _parse_tool_versions(text: str) -> dict[str, str]:
    """Parse asdf/mise `.tool-versions` content into a pin dict.

    Lines are `<plugin> <version> [fallback_version ...]`. `#` starts a
    comment. Unknown plugins and malformed lines are silently dropped.
    """
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        key = _TOOL_VERSIONS_ALIASES.get(parts[0].lower())
        if key is None:
            continue
        pins[key] = parts[1]
    return pins


def _read_single_version(path: Path) -> str | None:
    try:
        value = path.read_text().strip()
    except OSError:
        return None
    return value or None


def detect_versions(root: Path) -> dict[str, str]:
    """Return tool pins discovered from version files at ``root``.

    Only keys that appear in ``DEFAULT_VERSIONS`` are returned so the result
    is safe to merge into the ``--versions`` dict. Dedicated single-tool
    files (`.go-version`, `.terraform-version`) take precedence over
    `.tool-versions` since asdf itself applies them at higher priority.

    `.nvmrc` and `.python-version` are read (to signal awareness) but do not
    produce pins — node and python ship pre-installed on the target VM and
    are not in ``DEFAULT_VERSIONS``.
    """
    # Load DEFAULT_VERSIONS lazily to keep this module free of import-time
    # coupling to sections.py.
    from .sections import DEFAULT_VERSIONS

    pins: dict[str, str] = {}

    tool_versions = root / ".tool-versions"
    if tool_versions.exists():
        try:
            pins.update(_parse_tool_versions(tool_versions.read_text()))
        except OSError:
            pass

    go_version = _read_single_version(root / ".go-version")
    if go_version is not None:
        pins["go"] = go_version.split()[0]

    tf_version = _read_single_version(root / ".terraform-version")
    if tf_version is not None:
        pins["terraform"] = tf_version.split()[0]

    # .nvmrc / .python-version: touched for awareness, no pin emitted.
    (root / ".nvmrc").exists()
    (root / ".python-version").exists()

    return {k: v for k, v in pins.items() if k in DEFAULT_VERSIONS}
