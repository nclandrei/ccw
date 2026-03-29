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

## Options

```
uvx ccweb init --toolchains node,python       # Just Node + Python
uvx ccweb init --toolchains go --extras gh    # Go with gh CLI
uvx ccweb init --force                        # Overwrite existing files
uvx ccweb init --scripts-dir ci/scripts       # Custom scripts directory
```

### Toolchains

`node`, `python`, `go`, `rust`, `ruby`, `java` — default: all

### Extras

`gh`, `uv`, `pnpm`, `yarn`, `bun`, `browser` — default: all

## How it works

1. **`setup.sh`** runs once when a new VM is created. Installs system packages, toolchains, and persists environment variables to `/etc/environment`.

2. **`session-start.sh`** runs on every session start (new + resumed). Sources env vars, detects project lockfiles, and installs dependencies. Auto-runs `setup.sh` if the VM hasn't been provisioned yet.

3. **`diagnose.sh`** checks what's installed, what's missing, and what's misconfigured.

4. **`.claude/settings.json`** wires the SessionStart hook so `session-start.sh` runs automatically.

## Web configurator

Use the interactive configurator at **[ccweb.nicolaeandrei.com](https://ccweb.nicolaeandrei.com)** to pick toolchains and copy the command.

## License

MIT
