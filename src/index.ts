import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { InputDialog } from '@jupyterlab/apputils';

import { CodeCell } from '@jupyterlab/cells';

import * as nbformat from '@jupyterlab/nbformat';

import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';

import { requestAPI } from './handler';

/**
 * CSS class names used by the extension.
 */
const EXPLAIN_BUTTON_CLASS = 'ipyexplain-explain-btn';
const FIX_BUTTON_CLASS = 'ipyexplain-fix-btn';
const GENERATE_BUTTON_CLASS = 'ipyexplain-generate-btn';
const ERROR_BUTTONS_CLASS = 'ipyexplain-error-buttons';
const GENERATE_CONTAINER_CLASS = 'ipyexplain-generate-container';

/**
 * Add the "Generate Code" button below the input area of a code cell.
 */
function addGenerateButton(cell: CodeCell): void {
  const node = cell.node;

  // Avoid adding multiple buttons
  if (node.querySelector('.' + GENERATE_CONTAINER_CLASS)) {
    return;
  }

  const container = document.createElement('div');
  container.className = GENERATE_CONTAINER_CLASS;

  const btn = document.createElement('button');
  btn.className = GENERATE_BUTTON_CLASS;
  btn.textContent = '✨ Generate Code';
  btn.title = 'Generate code using an AI prompt';

  btn.addEventListener('click', async () => {
    const result = await InputDialog.getText({
      title: 'Generate Code',
      label: 'Enter a prompt describing the code you want to generate:',
      placeholder: 'e.g. read a CSV file and plot a histogram'
    });

    if (!result.button.accept || !result.value) {
      return;
    }

    btn.textContent = '⏳ Generating...';
    btn.disabled = true;

    try {
      const response = await requestAPI<{ code: string }>('generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: result.value })
      });

      // Insert generated code into the cell
      const model = cell.model;
      const currentSource = model.sharedModel.getSource();
      const newSource = currentSource
        ? currentSource + '\n\n' + response.code
        : response.code;
      model.sharedModel.setSource(newSource);
    } catch (err) {
      console.error('ipyexplain: generate failed', err);
      window.alert(
        'Failed to generate code. Check that OPENAI_API_KEY is set.\n\n' + err
      );
    } finally {
      btn.textContent = '✨ Generate Code';
      btn.disabled = false;
    }
  });

  container.appendChild(btn);

  // Insert after the input wrapper
  const inputWrapper = node.querySelector('.jp-Cell-inputWrapper');
  if (inputWrapper && inputWrapper.parentNode) {
    inputWrapper.parentNode.insertBefore(
      container,
      inputWrapper.nextSibling
    );
  } else {
    node.appendChild(container);
  }
}

/**
 * Extract error information from a code cell's outputs.
 * Returns null if no error is present.
 */
function extractError(
  cell: CodeCell
): { ename: string; evalue: string; traceback: string } | null {
  const outputs = cell.model.outputs;
  for (let i = 0; i < outputs.length; i++) {
    const outputJSON = outputs.get(i).toJSON();
    if (nbformat.isError(outputJSON)) {
      return {
        ename: outputJSON.ename,
        evalue: outputJSON.evalue,
        traceback: outputJSON.traceback.join('\n')
      };
    }
  }
  return null;
}

/**
 * Add or remove "Explain" and "Fix" buttons depending on whether there is
 * an error in the cell's output.
 */
function updateErrorButtons(cell: CodeCell): void {
  const node = cell.node;

  // Remove existing error buttons
  const existing = node.querySelector('.' + ERROR_BUTTONS_CLASS);
  if (existing) {
    existing.remove();
  }

  const errorInfo = extractError(cell);
  if (!errorInfo) {
    return;
  }

  const container = document.createElement('div');
  container.className = ERROR_BUTTONS_CLASS;

  // --- Explain button ---
  const explainBtn = document.createElement('button');
  explainBtn.className = EXPLAIN_BUTTON_CLASS;
  explainBtn.textContent = '💡 Explain';
  explainBtn.title = 'Explain this error using AI';

  explainBtn.addEventListener('click', async () => {
    explainBtn.textContent = '⏳ Explaining...';
    explainBtn.disabled = true;

    try {
      const response = await requestAPI<{ explanation: string }>('explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ename: errorInfo.ename,
          evalue: errorInfo.evalue,
          traceback: errorInfo.traceback
        })
      });

      // Show the explanation in a panel below the buttons
      let explanationDiv = container.querySelector(
        '.ipyexplain-explanation'
      ) as HTMLDivElement | null;
      if (!explanationDiv) {
        explanationDiv = document.createElement('div');
        explanationDiv.className = 'ipyexplain-explanation';
        container.appendChild(explanationDiv);
      }
      explanationDiv.textContent = response.explanation;
      explanationDiv.style.display = 'block';
    } catch (err) {
      console.error('ipyexplain: explain failed', err);
      window.alert(
        'Failed to explain error. Check that OPENAI_API_KEY is set.\n\n' + err
      );
    } finally {
      explainBtn.textContent = '💡 Explain';
      explainBtn.disabled = false;
    }
  });

  // --- Fix button ---
  const fixBtn = document.createElement('button');
  fixBtn.className = FIX_BUTTON_CLASS;
  fixBtn.textContent = '🔧 Fix';
  fixBtn.title = 'Fix this error using AI';

  fixBtn.addEventListener('click', async () => {
    fixBtn.textContent = '⏳ Fixing...';
    fixBtn.disabled = true;

    try {
      const code = cell.model.sharedModel.getSource();
      const response = await requestAPI<{ fixed_code: string }>('fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          ename: errorInfo.ename,
          evalue: errorInfo.evalue,
          traceback: errorInfo.traceback
        })
      });

      // Replace the cell's code with the fixed code
      cell.model.sharedModel.setSource(response.fixed_code);
    } catch (err) {
      console.error('ipyexplain: fix failed', err);
      window.alert(
        'Failed to fix code. Check that OPENAI_API_KEY is set.\n\n' + err
      );
    } finally {
      fixBtn.textContent = '🔧 Fix';
      fixBtn.disabled = false;
    }
  });

  container.appendChild(explainBtn);
  container.appendChild(fixBtn);

  // Insert after the output wrapper (or at end of cell)
  const outputWrapper = node.querySelector('.jp-Cell-outputWrapper');
  if (outputWrapper && outputWrapper.parentNode) {
    outputWrapper.parentNode.insertBefore(container, outputWrapper.nextSibling);
  } else {
    node.appendChild(container);
  }
}

/**
 * Set up watching for a single code cell.
 */
function watchCell(cell: CodeCell, watchedCells: WeakSet<CodeCell>): void {
  if (watchedCells.has(cell)) {
    return;
  }
  watchedCells.add(cell);

  addGenerateButton(cell);

  cell.model.outputs.changed.connect(() => {
    updateErrorButtons(cell);
  });
}

/**
 * Connect to a notebook panel and start watching its cells.
 */
function connectNotebook(
  panel: NotebookPanel,
  watchedCells: WeakSet<CodeCell>
): void {
  const notebook = panel.content;

  const watchAllCells = () => {
    for (const widget of notebook.widgets) {
      if (widget instanceof CodeCell) {
        watchCell(widget, watchedCells);
      }
    }
  };

  // Watch already-existing cells
  watchAllCells();

  // Watch newly added cells
  notebook.model?.cells.changed.connect(watchAllCells);
}

/**
 * Main JupyterLab plugin.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'ipyexplain:plugin',
  description:
    'Adds AI-powered Explain, Fix, and Generate buttons to notebook cells',
  autoStart: true,
  requires: [INotebookTracker],
  activate: (app: JupyterFrontEnd, tracker: INotebookTracker) => {
    console.log('JupyterLab extension ipyexplain is activated!');

    const watchedCells = new WeakSet<CodeCell>();

    tracker.widgetAdded.connect((_, panel) => {
      connectNotebook(panel, watchedCells);
    });

    // Handle already-open notebooks
    if (tracker.currentWidget) {
      connectNotebook(tracker.currentWidget, watchedCells);
    }
  }
};

export default plugin;
