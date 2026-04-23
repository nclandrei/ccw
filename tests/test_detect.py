"""Tests for ccw.detect — auto-detection of toolchains/extras from a project root."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw.detect import detect_extras, detect_toolchains  # noqa: E402


class _TmpRoot:
    """Context manager: yields a Path to a fresh temporary directory."""

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        return Path(self._tmp.name)

    def __exit__(self, *exc):
        self._tmp.cleanup()


def _touch(root: Path, *relpaths: str) -> None:
    for rel in relpaths:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")


def _write(root: Path, relpath: str, content: str) -> None:
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


class DetectToolchainsTests(unittest.TestCase):
    def test_empty_directory_detects_nothing(self):
        with _TmpRoot() as root:
            self.assertEqual(detect_toolchains(root), set())

    def test_package_json_detects_node(self):
        with _TmpRoot() as root:
            _touch(root, "package.json")
            self.assertEqual(detect_toolchains(root), {"node"})

    def test_lockfiles_detect_node(self):
        for lockfile in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb"):
            with _TmpRoot() as root:
                _touch(root, lockfile)
                self.assertIn("node", detect_toolchains(root), f"{lockfile} should imply node")

    def test_pyproject_detects_python(self):
        with _TmpRoot() as root:
            _touch(root, "pyproject.toml")
            self.assertEqual(detect_toolchains(root), {"python"})

    def test_requirements_txt_detects_python(self):
        with _TmpRoot() as root:
            _touch(root, "requirements.txt")
            self.assertIn("python", detect_toolchains(root))

    def test_setup_py_detects_python(self):
        with _TmpRoot() as root:
            _touch(root, "setup.py")
            self.assertIn("python", detect_toolchains(root))

    def test_go_mod_detects_go(self):
        with _TmpRoot() as root:
            _touch(root, "go.mod")
            self.assertEqual(detect_toolchains(root), {"go"})

    def test_cargo_toml_detects_rust(self):
        with _TmpRoot() as root:
            _touch(root, "Cargo.toml")
            self.assertEqual(detect_toolchains(root), {"rust"})

    def test_gemfile_detects_ruby(self):
        with _TmpRoot() as root:
            _touch(root, "Gemfile")
            self.assertEqual(detect_toolchains(root), {"ruby"})

    def test_gemspec_detects_ruby(self):
        with _TmpRoot() as root:
            _touch(root, "mygem.gemspec")
            self.assertIn("ruby", detect_toolchains(root))

    def test_pom_xml_detects_java(self):
        with _TmpRoot() as root:
            _touch(root, "pom.xml")
            self.assertEqual(detect_toolchains(root), {"java"})

    def test_gradle_detects_java(self):
        with _TmpRoot() as root:
            _touch(root, "build.gradle")
            self.assertIn("java", detect_toolchains(root))

    def test_gradle_kts_detects_java(self):
        with _TmpRoot() as root:
            _touch(root, "build.gradle.kts")
            self.assertIn("java", detect_toolchains(root))

    def test_deno_json_detects_deno(self):
        with _TmpRoot() as root:
            _touch(root, "deno.json")
            self.assertEqual(detect_toolchains(root), {"deno"})

    def test_deno_jsonc_detects_deno(self):
        with _TmpRoot() as root:
            _touch(root, "deno.jsonc")
            self.assertIn("deno", detect_toolchains(root))

    def test_mix_exs_detects_elixir(self):
        with _TmpRoot() as root:
            _touch(root, "mix.exs")
            self.assertEqual(detect_toolchains(root), {"elixir"})

    def test_build_zig_detects_zig(self):
        with _TmpRoot() as root:
            _touch(root, "build.zig")
            self.assertEqual(detect_toolchains(root), {"zig"})

    def test_csproj_detects_dotnet(self):
        with _TmpRoot() as root:
            _touch(root, "MyApp.csproj")
            self.assertIn("dotnet", detect_toolchains(root))

    def test_fsproj_detects_dotnet(self):
        with _TmpRoot() as root:
            _touch(root, "MyApp.fsproj")
            self.assertIn("dotnet", detect_toolchains(root))

    def test_sln_detects_dotnet(self):
        with _TmpRoot() as root:
            _touch(root, "Solution.sln")
            self.assertIn("dotnet", detect_toolchains(root))

    def test_composer_json_detects_php(self):
        with _TmpRoot() as root:
            _touch(root, "composer.json")
            self.assertEqual(detect_toolchains(root), {"php"})

    def test_polyglot_repo_combines(self):
        with _TmpRoot() as root:
            _touch(root, "package.json", "pyproject.toml", "go.mod", "Cargo.toml")
            self.assertEqual(detect_toolchains(root), {"node", "python", "go", "rust"})


class DetectExtrasTests(unittest.TestCase):
    def test_empty_directory_detects_nothing(self):
        with _TmpRoot() as root:
            self.assertEqual(detect_extras(root), set())

    def test_pnpm_lock_detects_pnpm(self):
        with _TmpRoot() as root:
            _touch(root, "pnpm-lock.yaml")
            self.assertIn("pnpm", detect_extras(root))

    def test_yarn_lock_detects_yarn(self):
        with _TmpRoot() as root:
            _touch(root, "yarn.lock")
            self.assertIn("yarn", detect_extras(root))

    def test_bun_lock_detects_bun(self):
        with _TmpRoot() as root:
            _touch(root, "bun.lock")
            self.assertIn("bun", detect_extras(root))

    def test_bun_lockb_detects_bun(self):
        with _TmpRoot() as root:
            _touch(root, "bun.lockb")
            self.assertIn("bun", detect_extras(root))

    def test_uv_lock_detects_uv(self):
        with _TmpRoot() as root:
            _touch(root, "uv.lock")
            self.assertIn("uv", detect_extras(root))

    def test_pyproject_with_tool_uv_detects_uv(self):
        with _TmpRoot() as root:
            _write(root, "pyproject.toml", "[tool.uv]\ndev-dependencies = []\n")
            self.assertIn("uv", detect_extras(root))

    def test_pyproject_without_tool_uv_does_not_detect_uv(self):
        with _TmpRoot() as root:
            _write(root, "pyproject.toml", "[project]\nname = 'x'\n")
            self.assertNotIn("uv", detect_extras(root))

    def test_playwright_in_package_json_detects_browser(self):
        with _TmpRoot() as root:
            _write(root, "package.json", '{"devDependencies": {"playwright": "^1.0.0"}}')
            self.assertIn("browser", detect_extras(root))

    def test_puppeteer_in_package_json_detects_browser(self):
        with _TmpRoot() as root:
            _write(root, "package.json", '{"dependencies": {"puppeteer": "^21.0.0"}}')
            self.assertIn("browser", detect_extras(root))

    def test_plain_package_json_does_not_detect_browser(self):
        with _TmpRoot() as root:
            _write(root, "package.json", '{"dependencies": {"react": "^18.0.0"}}')
            self.assertNotIn("browser", detect_extras(root))

    def test_dockerfile_detects_docker(self):
        with _TmpRoot() as root:
            _touch(root, "Dockerfile")
            self.assertIn("docker", detect_extras(root))

    def test_compose_yaml_detects_docker(self):
        for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            with _TmpRoot() as root:
                _touch(root, name)
                self.assertIn("docker", detect_extras(root), f"{name} should imply docker")

    def test_postgres_in_compose_detects_postgres(self):
        with _TmpRoot() as root:
            _write(root, "docker-compose.yml", "services:\n  db:\n    image: postgres:16\n")
            self.assertIn("postgres", detect_extras(root))

    def test_redis_in_compose_detects_redis(self):
        with _TmpRoot() as root:
            _write(root, "compose.yml", "services:\n  cache:\n    image: redis:7\n")
            self.assertIn("redis", detect_extras(root))

    def test_terraform_file_detects_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "main.tf")
            self.assertIn("cloud", detect_extras(root))

    def test_tfvars_file_detects_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "prod.tfvars")
            self.assertIn("cloud", detect_extras(root))

    def test_terraform_in_subdirectory_detects_cloud(self):
        # Terraform configs are commonly nested under terraform/ or infra/
        with _TmpRoot() as root:
            _touch(root, "terraform/main.tf")
            self.assertIn("cloud", detect_extras(root))

    def test_helm_chart_detects_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "Chart.yaml")
            self.assertIn("cloud", detect_extras(root))

    def test_helmfile_detects_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "helmfile.yaml")
            self.assertIn("cloud", detect_extras(root))

    def test_kubeconfig_detects_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "kubeconfig")
            self.assertIn("cloud", detect_extras(root))

    def test_k8s_manifests_dir_detects_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "k8s/deployment.yaml")
            self.assertIn("cloud", detect_extras(root))

    def test_kustomization_detects_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "kustomization.yaml")
            self.assertIn("cloud", detect_extras(root))

    def test_plain_repo_does_not_detect_cloud(self):
        with _TmpRoot() as root:
            _touch(root, "package.json", "Dockerfile", "README.md")
            self.assertNotIn("cloud", detect_extras(root))

    def test_yaml_without_k8s_does_not_detect_cloud(self):
        # A bare config.yaml at root shouldn't imply cloud
        with _TmpRoot() as root:
            _touch(root, "config.yaml", "settings.yml")
            self.assertNotIn("cloud", detect_extras(root))


if __name__ == "__main__":
    unittest.main()
