# ccweb

Bootstrap [Claude Code](https://claude.ai/code) web environments with one command.

```
uvx ccweb init
```

Generates `setup.sh`, `session-start.sh`, `diagnose.sh`, and wires `.claude/settings.json` for your project. When you start a Claude Code web session, the VM is automatically provisioned with your selected toolchains.

## Quick start

```bash
# In your project root
uvx ccweb init

# Commit and push
git add scripts/ .claude/settings.json
git commit -m "Add Claude Code web environment setup"
git push

# Start a Claude Code web session — it auto-provisions
# Then verify:
uvx ccweb doctor
```

## Local Docker validation

Before pushing, validate the generated scripts against a clean Ubuntu 24.04 container:

```bash
uvx ccweb test                    # runs setup.sh + diagnose.sh in ubuntu:24.04
uvx ccweb test --image ubuntu:22.04
uvx ccweb test --shell            # interactive shell for ad-hoc debugging
```

Requires a local Docker daemon. The repo is mounted read-only at `/workspace`, so the test can never modify your working copy.

## Options

```
uvx ccweb init --toolchains auto --extras auto    # Detect from repo files
uvx ccweb init --toolchains node,python           # Just Node + Python
uvx ccweb init --toolchains go --extras postgres  # Go + psql
uvx ccweb init --versions go=1.23.0,zig=0.14.0    # Pin tool versions
uvx ccweb init --env-file .env.example            # Declare required env vars
uvx ccweb init --env-file ""                      # Disable env-file auto-detect
uvx ccweb init --force                            # Overwrite existing files
uvx ccweb init --scripts-dir ci/scripts           # Custom scripts directory
uvx ccweb init --skills ai/skills                 # Custom skills directory
uvx ccweb init --skills ""                        # Disable skills wiring
```

### Toolchains

`node`, `python`, `go`, `rust`, `ruby`, `java`, `deno`, `elixir`, `zig`, `dotnet`, `php` — default: all

### Extras

`uv`, `pnpm`, `yarn`, `bun`, `browser`, `postgres`, `redis`, `docker` — default: all

`gh`, `duckdb`, `yq`, `sqlite3`, `jq`, `pandoc`, `shellcheck`, and friends are always installed — no flag needed.

### Auto-detection

Pass `auto` to either flag to install only what the repo actually needs. Detection inspects the project root for marker files:

| Toolchain | Markers                                                                        |
| --------- | ------------------------------------------------------------------------------ |
| `node`    | `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock` |
| `python`  | `pyproject.toml`, `requirements.txt`, `setup.py`, `Pipfile`, `uv.lock`         |
| `go`      | `go.mod`                                                                       |
| `rust`    | `Cargo.toml`                                                                   |
| `ruby`    | `Gemfile`, `*.gemspec`                                                         |
| `java`    | `pom.xml`, `build.gradle`, `build.gradle.kts`                                  |
| `deno`    | `deno.json`, `deno.jsonc`                                                      |
| `elixir`  | `mix.exs`                                                                      |
| `zig`     | `build.zig`, `build.zig.zon`                                                   |
| `dotnet`  | `*.csproj`, `*.fsproj`, `*.sln`                                                |
| `php`     | `composer.json`                                                                |

Extras are detected from lockfiles, `Dockerfile` / `docker-compose.yml`, `playwright`/`puppeteer` in `package.json`, `[tool.uv]` in `pyproject.toml`, and `postgres`/`redis` images referenced in compose files.

The `cloud` extra (aws, gcloud, terraform, kubectl, helm) is detected from any of: `*.tf` / `*.tfvars` at the root, a `terraform/` / `infra/` / `iac/` / `k8s/` / `kubernetes/` / `manifests/` directory, or a `Chart.yaml`, `helmfile.yaml`, `kubeconfig`, or `kustomization.yaml` file at the root.

### Version pinning

Override any of the baked-in versions with `--versions KEY=VALUE` (comma-separated for multiple). Unspecified tools use the defaults in `DEFAULT_VERSIONS`.

Valid keys: `go`, `zig`, `gh`, `duckdb`, `yq`, `dotnet_channel`, `terraform`, `kubectl`.

```
uvx ccweb init --versions go=1.23.0
uvx ccweb init --versions go=1.23.0,gh=2.74.1,dotnet_channel=LTS
```

Pins are also auto-detected from common version files at the project root — no flag required:

| File                        | Source of pin                                                         |
| --------------------------- | --------------------------------------------------------------------- |
| `.tool-versions`            | asdf/mise entries for `golang`/`go`, `zig`, `terraform`, `kubectl`    |
| `.go-version`               | Go (takes precedence over `.tool-versions`)                           |
| `.terraform-version`        | Terraform (takes precedence over `.tool-versions`)                    |
| `.nvmrc`, `.python-version` | Read but ignored — node and python are pre-installed and not pinnable |

Explicit `--versions` entries always win over auto-detected pins, per key.

### Environment variables

If the repo contains `.env.example` or `.env.template` (or you point `--env-file` somewhere else), `session-start.sh` reads the variable **names** from it and warns when any are unset in the session. `diagnose.sh` gets a matching section that shows each declared variable as set or missing.

The file is treated as a schema — ccweb never reads, copies, or transmits the values. Store actual secrets in the claude.ai/code Environment Variables UI at the project level.

```
# .env.example (checked into the repo; values are placeholders)
DATABASE_URL=
OPENAI_API_KEY=
STRIPE_SECRET=
```

Pass `--env-file ""` to disable auto-detection.

### Skills

By default, ccweb looks for Claude Code skills in `.claude/skills/` in your
repo (each subdirectory holds a `SKILL.md`). On session start, every skill
found there is symlinked into `~/.claude/skills/<name>` so Claude Code
discovers them at the user level across every session on the VM. Pass
`--skills ai/skills` for a custom path, or `--skills ""` to disable.

```
<repo>/<DIR>/my-skill/SKILL.md
<repo>/<DIR>/my-skill/reference.md
```

## How it works

1. **`setup.sh`** runs once when a new VM is created. Installs system packages, toolchains, and persists environment variables to `/etc/environment`.

2. **`session-start.sh`** runs on every session start (new + resumed). Sources env vars, detects project lockfiles, and installs dependencies. Auto-runs `setup.sh` if the VM hasn't been provisioned yet.

3. **`diagnose.sh`** checks what's installed, what's missing, and what's misconfigured.

4. **`.claude/settings.json`** wires the SessionStart hook so `session-start.sh` runs automatically.

## License

MIT
