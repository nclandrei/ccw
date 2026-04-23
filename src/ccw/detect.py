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
    "php": ("composer.json",),
}

# Toolchain → list of glob patterns (used when the marker filename varies).
_TOOLCHAIN_GLOBS: dict[str, tuple[str, ...]] = {
    "ruby": ("*.gemspec",),
    "dotnet": ("*.csproj", "*.fsproj", "*.sln"),
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
        if '"playwright"' in text or '"puppeteer"' in text or '"@playwright/test"' in text:
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

    return found
