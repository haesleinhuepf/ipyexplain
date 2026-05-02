# jupyter-vibe-coding

A JupyterLab 4.x extension that adds AI-powered buttons to notebook cells

![](https://github.com/haesleinhuepf/ipyexplain/blob/main/docs/images/screenshot.png?raw=true)

- **💡 Explain** – when a cell throws an error, click *Explain* to get a plain-language description of what went wrong, powered by an LLM via OpenAI's API.
- **🔧 Fix** – click *Fix* to automatically replace the erroneous cell code with an LLM-corrected version.
- **🪄 Generate Code** – a command (`jupyter-vibe-coding:generate-code`) is contributed to the Cell toolbar via `jupyter.lab.toolbars`; it opens a prompt dialog and replaces the current code cell with generated code.

---

## Installation

```bash
pip install jupyter-vibe-coding
```

This installs both the Python server extension and the pre-built JupyterLab
frontend extension.

You also need an **OpenAI API key** exported as an environment variable:

```bash
export OPENAI_API_KEY=sk-...
```

Alternatively, you can use environment variables to configure a different OpenAI-API compatible LLM server, including local installations using [ollama](https://ollama.com):

```bash
# Preferred API key variable (falls back to OPENAI_API_KEY)
export JUPYTER_VIBE_CODING_API_KEY=sk-key...

# Optional custom OpenAI-compatible endpoint
export JUPYTER_VIBE_CODING_BASE_URL=http://localhost:11434/v1

# Optional model override (default: gpt-4o-mini)
export JUPYTER_VIBE_CODING_MODEL=gpt-oss:20b
```

### Development install

The development install works on Windows, macOS, and Linux without requiring
Administrator/Developer Mode privileges.

```bash
git clone https://github.com/haesleinhuepf/jupyter-vibe-coding.git
cd jupyter-vibe-coding

# 1. Install JupyterLab and build tools
pip install jupyterlab

# 2. Install JS dependencies
jlpm install

# 3. Build the frontend extension
jlpm run build

# 4. Install the Python package in editable mode
#    This also registers the server extension automatically.
pip install -e ".[test]"
```

After these steps, start JupyterLab normally:

```bash
jupyter lab
```

Verify both extensions are detected:

```bash
jupyter server extension list
jupyter labextension list
```

You should see `jupyter_vibe_coding` in the server list and
`jupyter-vibe-coding` in the labextension list.

To pick up TypeScript source changes during development, rebuild and restart:

```bash
jlpm run build
jupyter lab
```

---

## Usage

1. Start JupyterLab: `jupyter lab`
2. Open or create a Python notebook.
3. Run a cell that contains an error – **💡 Explain** and **🔧 Fix** buttons
   appear below the output.
4. Click **🪄 Generate Code** in the Cell toolbar to open the prompt dialog.

---

## Architecture

```
jupyter-vibe-coding/
├── src/
│   ├── index.ts      # JupyterLab plugin (frontend)
│   └── handler.ts    # Helper for calling the Jupyter server REST API
├── style/
│   └── index.css     # Button styles
├── jupyter_vibe_coding/
│   ├── __init__.py   # Server extension registration
│   ├── handlers.py   # Tornado handlers + LLM helper functions
│   └── tests/
│       └── test_handlers.py
├── package.json
├── tsconfig.json
└── pyproject.toml
```

### API endpoints

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/jupyter-vibe-coding/explain` | `{ename, evalue, traceback}` | `{explanation}` |
| POST | `/jupyter-vibe-coding/fix` | `{code, ename, evalue, traceback}` | `{fixed_code, fix_summary}` |
| POST | `/jupyter-vibe-coding/generate` | `{prompt}` | `{code}` |

---

## Running the tests

```bash
pip install -e ".[test]"
pytest jupyter_vibe_coding/tests/ -v
```

---

## License

BSD 3-Clause – see [LICENSE](LICENSE).