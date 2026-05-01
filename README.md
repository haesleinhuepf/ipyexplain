# ipyexplain

A JupyterLab 4.x extension that adds AI-powered buttons to notebook cells:

- **💡 Explain** – when a cell throws an error, click *Explain* to get a plain-language description of what went wrong, powered by an LLM via OpenAI's API.
- **🔧 Fix** – click *Fix* to automatically replace the erroneous cell code with an LLM-corrected version.
- **✨ Generate Code** – every code cell has a *Generate Code* button that opens a prompt dialog; the LLM writes code from your description and inserts it into the cell.

---

## Requirements

| Component | Version |
|-----------|---------|
| JupyterLab | ≥ 4.0, < 5 |
| Python | ≥ 3.8 |
| openai | ≥ 1.0 |

You also need an **OpenAI API key** exported as an environment variable:

```bash
export OPENAI_API_KEY=sk-...
```

---

## Installation

```bash
pip install ipyexplain
```

This installs both the Python server extension and the pre-built JupyterLab
frontend extension.

### Development install

The development install works on Windows, macOS, and Linux without requiring
Administrator/Developer Mode privileges.

```bash
git clone https://github.com/haesleinhuepf/ipyexplain.git
cd ipyexplain

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

> **Note for Windows users:** Do *not* run `jupyter labextension develop . --overwrite`
> — that command requires Developer Mode for symlink creation. The steps above
> copy the pre-built extension into the package directory, so no symlinks are needed.

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
4. Click **✨ Generate Code** in any code cell to open the prompt dialog.

---

## Architecture

```
ipyexplain/
├── src/
│   ├── index.ts      # JupyterLab plugin (frontend)
│   └── handler.ts    # Helper for calling the Jupyter server REST API
├── style/
│   └── index.css     # Button styles
├── ipyexplain/
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
| POST | `/ipyexplain/explain` | `{ename, evalue, traceback}` | `{explanation}` |
| POST | `/ipyexplain/fix` | `{code, ename, evalue, traceback}` | `{fixed_code}` |
| POST | `/ipyexplain/generate` | `{prompt}` | `{code}` |

---

## Running the tests

```bash
pip install -e ".[test]"
pytest ipyexplain/tests/ -v
```

---

## License

BSD 3-Clause – see [LICENSE](LICENSE).