# Local Agent — Mac Mini Setup Notes

Hard-won environment facts for `macmini.local` (Apple M4, 24GB). Read before running anything.

## This machine IS the Mac Mini

`ssh macmini` loops back to localhost — the dev box and the server are the same machine (`hostname` = `macmini.local`). Run commands directly; no SSH needed.

## Python: use `python3.13`, not `python3`

The default `python3` was a broken Homebrew `python@3.14` (pyexpat dylib symbol error). It was removed as a side effect of `brew uninstall ollama`. Use the explicit interpreter:

```
/opt/homebrew/bin/python3.13   # 3.13.12, works; project target
```

`openai` is installed here via `python3.13 -m pip install --break-system-packages openai`.

## Ollama: formula CLI + cask runner (the working combo)

Neither Homebrew route works alone on this box:

- **Formula** (`brew install ollama`): CLI + server work **only when started via launchd** (`brew services start ollama`). Running `ollama serve` directly in the Claude Code Bash tool **hangs** — the bash sandbox blocks the server from binding the port. The formula also ships **without** the `llama-server` runner (inference fails with "llama-server binary not found").
- **Cask** (`brew install --cask ollama-app`): bundles a complete runtime (`llama-server` + dylibs) but its CLI binary **hangs on every invocation** (even `--version`) in this exec context.

**Working setup = formula + cask's runner copied in:**

```bash
brew install ollama
brew install --cask ollama-app           # only needed to obtain the runner files
DST=/opt/homebrew/Cellar/ollama/<ver>/libexec/lib/ollama
SRC=/Applications/Ollama.app/Contents/Resources
cp -a "$SRC"/llama-server "$DST"/
cp -a "$SRC"/libllama*.dylib "$SRC"/libggml*.dylib "$SRC"/libmtmd*.dylib "$DST"/
brew services restart ollama             # launchd; binds 11434 outside the bash sandbox
curl -s http://localhost:11434/api/version   # confirm up
```

Models live in `~/.ollama/models` (shared across formula/cask — no re-download). `qwen3:14b` is pulled.

## Smoke test

```bash
/opt/homebrew/bin/python3.13 setup/local-agent/scripts/smoke_test.py
```

Expected: `PASS: model emits correct tool call`. First run ~22s (cold model load), warm ~10s/turn with thinking on. Set `think=false` for qwen3 to speed up and clean tool-call output.

## Implication for the agent

Tools/tests run under `python3.13` anywhere. The **Ollama server must be launchd-managed** (`brew services`), not started from the Bash tool. The custom loop (`agent.py`) and Goose talk to the already-running server over HTTP, so they're unaffected by the sandbox.
