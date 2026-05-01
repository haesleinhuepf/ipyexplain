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
const EXPLAIN_BUTTON_CLASS = 'jupyter-vibe-coding-explain-btn';
const FIX_BUTTON_CLASS = 'jupyter-vibe-coding-fix-btn';
const ERROR_BUTTONS_CLASS = 'jupyter-vibe-coding-error-buttons';
const GENERATE_COMMAND = 'jupyter-vibe-coding:generate-code';

async function generateCodeInCurrentCell(
  cell: CodeCell,
  setBusyState?: (busy: boolean) => void
): Promise<void> {
  const result = await InputDialog.getText({
    title: 'Generate Code',
    label: 'Enter a prompt describing the code you want to generate:',
    placeholder: 'e.g. read a CSV file and plot a histogram'
  });

  if (!result.button.accept || !result.value) {
    return;
  }

  setBusyState?.(true);

  try {
    const existingCode = cell.model.sharedModel.getSource();
    const response = await requestAPI<{ code: string }>('generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: result.value,
        existing_code: existingCode
      })
    });

    cell.model.sharedModel.setSource(response.code);
  } catch (err) {
    console.error('jupyter-vibe-coding: generate failed', err);
    window.alert(
      'Failed to generate code. Check that OPENAI_API_KEY is set.\n\n' + err
    );
  } finally {
    setBusyState?.(false);
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
        '.jupyter-vibe-coding-explanation'
      ) as HTMLDivElement | null;
      if (!explanationDiv) {
        explanationDiv = document.createElement('div');
        explanationDiv.className = 'jupyter-vibe-coding-explanation';
        container.appendChild(explanationDiv);
      }
      explanationDiv.textContent = response.explanation;
      explanationDiv.style.display = 'block';
    } catch (err) {
      console.error('jupyter-vibe-coding: explain failed', err);
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
      console.error('jupyter-vibe-coding: fix failed', err);
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
function watchCell(
  cell: CodeCell,
  watchedCells: WeakSet<CodeCell>
): void {
  if (watchedCells.has(cell)) {
    return;
  }
  watchedCells.add(cell);

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
  id: 'jupyter-vibe-coding:plugin',
  description:
    'Adds AI-powered Explain/Fix cell actions and notebook-level code generation',
  autoStart: true,
  requires: [INotebookTracker],
  activate: (app: JupyterFrontEnd, tracker: INotebookTracker) => {
    console.log('JupyterLab extension jupyter-vibe-coding is activated!');

    app.commands.addCommand(GENERATE_COMMAND, {
      label: '🪄',
      caption: 'Generate code and replace the current code cell content',
      isEnabled: () => {
        const panel = tracker.currentWidget;
        const activeCell = panel?.content.activeCell;
        return !!(activeCell && activeCell instanceof CodeCell);
      },
      execute: async () => {
        const panel = tracker.currentWidget;
        const notebook = panel?.content;
        const activeCell = notebook?.activeCell;

        if (!notebook || !(activeCell instanceof CodeCell)) {
          window.alert('Select a code cell first.');
          return;
        }

        await generateCodeInCurrentCell(activeCell);
      }
    });

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
