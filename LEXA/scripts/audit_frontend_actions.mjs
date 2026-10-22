#!/usr/bin/env node
/**
 * Static UX safety audit for visible React controls.
 * This is intentionally conservative: it does not prove business behavior, but it
 * catches common dead buttons, default-submit forms, and links without destinations.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const webRoot = path.join(ROOT, "apps/web");
const requireFromWeb = createRequire(path.join(webRoot, "package.json"));
let ts;
try { ts = requireFromWeb("typescript"); }
catch {
  try { ts = require("/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js"); }
  catch { console.error("ERROR: TypeScript is required. Run npm ci in apps/web first."); process.exit(2); }
}

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) return ["node_modules", ".next", "e2e"].includes(entry.name) ? [] : walk(file);
    return /\.(tsx|ts)$/.test(file) && !file.endsWith(".d.ts") ? [file] : [];
  });
}
function tagName(tag) {
  if (ts.isIdentifier(tag)) return tag.text;
  if (ts.isPropertyAccessExpression(tag)) return `${tag.expression.getText()}.${tag.name.text}`;
  return tag.getText();
}
function attrsOf(opening) {
  const attrs = new Map();
  for (const item of opening.attributes.properties) {
    if (!ts.isJsxAttribute(item)) continue;
    attrs.set(item.name.getText(), item.initializer);
  }
  return attrs;
}
function lineOf(source, node) { return source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1; }
function hasAttr(attrs, name) { return attrs.has(name) && attrs.get(name) !== undefined; }
function literalTrue(attrs, name) {
  const init = attrs.get(name);
  return init && ts.isJsxExpression(init) && init.expression && init.expression.kind === ts.SyntaxKind.TrueKeyword;
}
function containingSubmittedForm(node) {
  let current = node.parent;
  while (current) {
    if (ts.isJsxElement(current)) {
      const opening = current.openingElement;
      if (tagName(opening.tagName).toLowerCase() === "form") return hasAttr(attrsOf(opening), "onSubmit");
    }
    if (ts.isFunctionLike(current) || ts.isSourceFile(current)) break;
    current = current.parent;
  }
  return false;
}

const files = [...new Set([...walk(path.join(webRoot, "app")), ...walk(path.join(webRoot, "components"))])];
const findings = [];
let jsxButtons = 0, forms = 0, links = 0;
for (const file of files) {
  const sourceText = fs.readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, sourceText, ts.ScriptTarget.Latest, true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  for (const diagnostic of source.parseDiagnostics) {
    findings.push({ file, line: lineOf(source, diagnostic), message: `TSX parse error: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, " ")}` });
  }
  const visit = (node) => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const name = tagName(node.tagName);
      const lower = name.toLowerCase();
      const attrs = attrsOf(node);
      if (lower === "button" || name === "Button" || name === "IconButton") {
        jsxButtons += 1;
        const isSubmit = String((attrs.get("type") && attrs.get("type").getText(source) || "")).replaceAll('"', "").replaceAll("'", "") === "submit";
        // The shared Button primitive intentionally forwards all event props via {...props};
        // audit call sites for explicit handlers and let this one implementation remain generic.
        const propForwardingPrimitive = path.relative(webRoot, file).replaceAll("\\", "/") === "components/ui.tsx"
          && node.attributes.properties.some((attribute) => ts.isJsxSpreadAttribute(attribute));
        if (!hasAttr(attrs, "onClick") && !(isSubmit && containingSubmittedForm(node)) && !literalTrue(attrs, "disabled") && !propForwardingPrimitive) {
          findings.push({ file, line: lineOf(source, node), message: `button-like control <${name}> has no onClick handler and is not a submitted form control` });
        }
      }
      if (lower === "form") {
        forms += 1;
        if (!hasAttr(attrs, "onSubmit")) findings.push({ file, line: lineOf(source, node), message: "form has no onSubmit handler" });
      }
      if (lower === "a" || name === "Link") {
        links += 1;
        if (!hasAttr(attrs, "href")) findings.push({ file, line: lineOf(source, node), message: `link-like control <${name}> has no href destination` });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
}
if (findings.length) {
  for (const finding of findings) console.error(`${path.relative(ROOT, finding.file)}:${finding.line}: ${finding.message}`);
  console.error(`FAIL: ${findings.length} control/parse issue(s) across ${files.length} TypeScript files.`);
  process.exit(1);
}
console.log(`PASS: ${files.length} TypeScript/TSX files parsed; ${jsxButtons} button-like controls, ${forms} forms, and ${links} links passed action/destination checks.`);
