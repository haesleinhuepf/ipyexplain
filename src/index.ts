import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { Dialog, showDialog } from '@jupyterlab/apputils';

import { CodeCell } from '@jupyterlab/cells';

import * as nbformat from '@jupyterlab/nbformat';

import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';

import { Widget } from '@lumino/widgets';

import { requestAPI } from './handler';

/**
 * CSS class names used by the extension.
 */
const EXPLAIN_BUTTON_CLASS = 'jupyter-vibe-coding-explain-btn';
const FIX_BUTTON_CLASS = 'jupyter-vibe-coding-fix-btn';
const ERROR_BUTTONS_CLASS = 'jupyter-vibe-coding-error-buttons';
const GENERATE_COMMAND = 'jupyter-vibe-coding:generate-code';
const ADVANCED_CONFIG_STORAGE_KEY = 'jupyter-vibe-coding:advanced-config';

interface AdvancedConfig {
  enabled: boolean;
  base_url: string;
  api_key: string;
  model: string;
}

interface GenerateDialogValue {
  prompt: string;
  config: AdvancedConfig;
}

function getStoredAdvancedConfig(): AdvancedConfig {
  try {
    const raw = window.localStorage.getItem(ADVANCED_CONFIG_STORAGE_KEY);
    if (!raw) {
      return {
        enabled: false,
        base_url: '',
        api_key: '',
        model: ''
      };
    }

    const parsed = JSON.parse(raw) as Partial<AdvancedConfig>;
    return {
      enabled: !!parsed.enabled,
      base_url: parsed.base_url ?? '',
      api_key: parsed.api_key ?? '',
      model: parsed.model ?? ''
    };
  } catch (err) {
    console.warn('jupyter-vibe-coding: failed to read advanced config', err);
    return {
      enabled: false,
      base_url: '',
      api_key: '',
      model: ''
    };
  }
}

function persistAdvancedConfig(config: AdvancedConfig): void {
  try {
    window.localStorage.setItem(ADVANCED_CONFIG_STORAGE_KEY, JSON.stringify(config));
  } catch (err) {
    console.warn('jupyter-vibe-coding: failed to persist advanced config', err);
  }
}

function buildRequestConfigPayload(config: AdvancedConfig):
  | {
      enabled: boolean;
      base_url?: string;
      api_key?: string;
      model?: string;
    }
  | undefined {
  if (!config.enabled) {
    return undefined;
  }

  return {
    enabled: true,
    base_url: config.base_url.trim() || undefined,
    api_key: config.api_key.trim() || undefined,
    model: config.model.trim() || undefined
  };
}

class GenerateDialogBody
  extends Widget
  implements Dialog.IBodyWidget<GenerateDialogValue>
{
  private readonly promptInput: HTMLTextAreaElement;
  private readonly advancedCheckbox: HTMLInputElement;
  private readonly advancedSection: HTMLDivElement;
  private readonly baseUrlInput: HTMLInputElement;
  private readonly apiKeyInput: HTMLInputElement;
  private readonly modelInput: HTMLInputElement;

  constructor(initialConfig: AdvancedConfig) {
    super({ node: Private.createGenerateDialogNode() });
    this.addClass('jupyter-vibe-coding-generate-dialog');

    const promptInput = this.node.querySelector(
      '[data-role="prompt"]'
    ) as HTMLTextAreaElement | null;
    const advancedCheckbox = this.node.querySelector(
      '[data-role="advanced-enabled"]'
    ) as HTMLInputElement | null;
    const advancedSection = this.node.querySelector(
      '[data-role="advanced-section"]'
    ) as HTMLDivElement | null;
    const baseUrlInput = this.node.querySelector(
      '[data-role="base-url"]'
    ) as HTMLInputElement | null;
    const apiKeyInput = this.node.querySelector(
      '[data-role="api-key"]'
    ) as HTMLInputElement | null;
    const modelInput = this.node.querySelector(
      '[data-role="model"]'
    ) as HTMLInputElement | null;

    if (
      !promptInput ||
      !advancedCheckbox ||
      !advancedSection ||
      !baseUrlInput ||
      !apiKeyInput ||
      !modelInput
    ) {
      throw new Error('Failed to build generate dialog body');
    }

    this.promptInput = promptInput;
    this.advancedCheckbox = advancedCheckbox;
    this.advancedSection = advancedSection;
    this.baseUrlInput = baseUrlInput;
    this.apiKeyInput = apiKeyInput;
    this.modelInput = modelInput;

    this.promptInput.placeholder = 'e.g. read a CSV file and plot a histogram';
    this.advancedCheckbox.checked = initialConfig.enabled;
    this.baseUrlInput.value = initialConfig.base_url;
    this.apiKeyInput.value = initialConfig.api_key;
    this.modelInput.value = initialConfig.model;

    this.promptInput.addEventListener('keydown', event => {
      if (
        event.key === 'Enter' &&
        (event.shiftKey || event.ctrlKey || event.metaKey)
      ) {
        event.preventDefault();
        this.submitDialog();
      }
    });

    this.advancedCheckbox.addEventListener('change', () => {
      this.updateAdvancedVisibility();
    });

    this.updateAdvancedVisibility();
  }

  getValue(): GenerateDialogValue {
    return {
      prompt: this.promptInput.value,
      config: {
        enabled: this.advancedCheckbox.checked,
        base_url: this.baseUrlInput.value,
        api_key: this.apiKeyInput.value,
        model: this.modelInput.value
      }
    };
  }

  private updateAdvancedVisibility(): void {
    this.advancedSection.style.display = this.advancedCheckbox.checked
      ? 'grid'
      : 'none';
  }

  private submitDialog(): void {
    const dialogNode = this.node.closest('.jp-Dialog');
    const acceptButton = dialogNode?.querySelector(
      '.jp-Dialog-button.jp-mod-accept'
    ) as HTMLButtonElement | null;
    acceptButton?.click();
  }
}

namespace Private {
  export function createGenerateDialogNode(): HTMLElement {
    const node = document.createElement('div');
    node.className = 'jupyter-vibe-coding-generate-dialog-body';
    node.innerHTML = `
      <label class="jupyter-vibe-coding-dialog-field">
        <span class="jupyter-vibe-coding-dialog-label">Prompt</span>
        <textarea data-role="prompt" rows="4"></textarea>
      </label>
      <label class="jupyter-vibe-coding-dialog-checkbox-row">
        <input data-role="advanced-enabled" type="checkbox" />
        <span>Advanced options</span>
      </label>
      <div data-role="advanced-section" class="jupyter-vibe-coding-advanced-section">
        <label class="jupyter-vibe-coding-dialog-field">
          <span class="jupyter-vibe-coding-dialog-label">Base URL</span>
          <input data-role="base-url" type="text" placeholder="https://api.openai.com/v1" />
        </label>
        <label class="jupyter-vibe-coding-dialog-field">
          <span class="jupyter-vibe-coding-dialog-label">API key</span>
          <input data-role="api-key" type="password" placeholder="sk-..." />
        </label>
        <label class="jupyter-vibe-coding-dialog-field">
          <span class="jupyter-vibe-coding-dialog-label">Model</span>
          <input data-role="model" type="text" placeholder="gpt-4o-mini" />
        </label>
      </div>
    `;
    return node;
  }
}

async function generateCodeInCurrentCell(
  cell: CodeCell,
  setBusyState?: (busy: boolean) => void
): Promise<void> {
  const initialConfig = getStoredAdvancedConfig();
  const result = await showDialog<GenerateDialogValue>({
    title: 'Generate Code',
    body: new GenerateDialogBody(initialConfig),
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'Generate' })]
  });

  if (!result.button.accept || !result.value?.prompt.trim()) {
    return;
  }

  persistAdvancedConfig(result.value.config);
  const requestConfig = buildRequestConfigPayload(result.value.config);

  setBusyState?.(true);

  try {
    const existingCode = cell.model.sharedModel.getSource();
    const response = await requestAPI<{ code: string }>('generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: result.value.prompt.trim(),
        existing_code: existingCode,
        config: requestConfig
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
      const requestConfig = buildRequestConfigPayload(getStoredAdvancedConfig());
      const response = await requestAPI<{ explanation: string }>('explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ename: errorInfo.ename,
          evalue: errorInfo.evalue,
          traceback: errorInfo.traceback,
          config: requestConfig
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
      const requestConfig = buildRequestConfigPayload(getStoredAdvancedConfig());
      const code = cell.model.sharedModel.getSource();
      const response = await requestAPI<{ fixed_code: string }>('fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          ename: errorInfo.ename,
          evalue: errorInfo.evalue,
          traceback: errorInfo.traceback,
          config: requestConfig
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
