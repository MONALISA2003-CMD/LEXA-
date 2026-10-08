#!/usr/bin/env bash
set -euo pipefail
python -m pytest -q
node apps/web/tests/visible-product-contract.test.mjs
node - <<'NODE'
const ts = require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript');
const fs = require('fs');
const path = require('path');
let count = 0;
function walk(dir) {
  for (const e of fs.readdirSync(dir, {withFileTypes:true})) {
    const p = path.join(dir, e.name);
    if (e.isDirectory() && !['node_modules','.next'].includes(e.name)) walk(p);
    else if (e.isFile() && /\.(ts|tsx)$/.test(e.name) && e.name !== 'next-env.d.ts') {
      count += 1;
      const source = fs.readFileSync(p, 'utf8');
      ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.Preserve, target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext }, fileName: p });
    }
  }
}
walk('apps/web');
if (count !== 25) throw new Error(`Unexpected frontend TypeScript file count: ${count}`);
console.log(`frontend TypeScript syntax contract: PASS (${count} files)`);
NODE
python - <<'PY'
from pathlib import Path
required=[
 'apps/web/components/app-shell.tsx',
 'apps/web/app/products/page.tsx',
 'apps/web/app/inventory/page.tsx',
 'apps/web/app/sales/page.tsx',
 'apps/web/app/customers/page.tsx',
 'apps/web/app/purchasing/page.tsx',
 'apps/web/app/intelligence/page.tsx',
 'apps/web/app/administration/page.tsx',
 'apps/web/app/settings/page.tsx',
]
missing=[p for p in required if not Path(p).exists()]
if missing: raise SystemExit(f'Missing Phase 3 UI files: {missing}')
print('LEXA v2.8 workspace convergence verification: PASS')
PY
