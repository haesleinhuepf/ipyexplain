const fs = require('fs');
const path = require('path');

const packageJsonPath = path.join(
  __dirname,
  '..',
  'jupyter_vibe_coding',
  'labextension',
  'package.json'
);

if (!fs.existsSync(packageJsonPath)) {
  process.exit(0);
}

const raw = fs.readFileSync(packageJsonPath, 'utf8');
const pkg = JSON.parse(raw);

const loadPath = pkg?.jupyterlab?._build?.load;
if (typeof loadPath !== 'string') {
  process.exit(0);
}

const normalized = loadPath.replace(/\\+/g, '/');
if (normalized !== loadPath) {
  pkg.jupyterlab._build.load = normalized;
  fs.writeFileSync(packageJsonPath, JSON.stringify(pkg, null, 2) + '\n', 'utf8');
  console.log(
    `Normalized jupyterlab._build.load path: ${loadPath} -> ${normalized}`
  );
}
