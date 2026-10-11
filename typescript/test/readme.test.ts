// Type-checks the README's TypeScript snippets against the SDK, then runs them in order against
// spec-shaped responses. Each snippet becomes a module that sees the reader's context
// (test/readme-client.ts), in which `extralt` resolves to the real SDK with a local client.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, expect, it } from 'vitest';

const README = readFileSync(new URL('../README.md', import.meta.url), 'utf8');
const CLIENT = fileURLToPath(new URL('./readme-client.js', import.meta.url));
const directory = mkdtempSync(join(tmpdir(), 'extralt-readme-'));
afterAll(() => rmSync(directory, { recursive: true, force: true }));

function snippetModule(snippet: string): string {
  const imports: string[] = [];
  const body: string[] = [];
  for (const line of snippet.trimEnd().split('\n')) {
    if (!line.startsWith('import ')) body.push(line);
    else if (line.includes(' from '))
      imports.push(line.replace(`from 'extralt'`, `from '${CLIENT}'`));
    else throw new Error(`write README imports on one line: ${line}`);
  }
  return [
    ...imports,
    `import * as reader from '${CLIENT}';`,
    '{',
    'const { Extralt, client, robot, run, variantId } = reader;',
    '{',
    ...body,
    '}',
    '}',
  ].join('\n');
}

const files = [...README.matchAll(/```ts\n([\s\S]*?)```/g)].map(([, snippet], index) => {
  const file = join(directory, `snippet-${index + 1}.mts`);
  writeFileSync(file, snippetModule(snippet ?? ''));
  return file;
});

it('finds the README snippets', () => {
  expect(files.length).toBeGreaterThan(0);
});

it('type-checks every snippet against the SDK', () => {
  const tsc = createRequire(import.meta.url).resolve('typescript/bin/tsc');
  const options = ['--noEmit', '--strict', '--noUncheckedIndexedAccess', '--skipLibCheck'];
  const target = ['--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext'];
  const libraries = ['--lib', 'ES2023', '--types', 'node'];
  try {
    execFileSync(process.execPath, [tsc, ...options, ...target, ...libraries, ...files], {
      cwd: fileURLToPath(new URL('..', import.meta.url)),
      encoding: 'utf8',
    });
  } catch (error) {
    throw new Error((error as { stdout?: string }).stdout || String(error));
  }
}, 60_000);

it('runs every snippet in order', async () => {
  writeFileSync(join(directory, 'catalog.csv'), 'sku,title\n1,Shoe\n');
  const cwd = process.cwd();
  process.chdir(directory);
  try {
    for (const file of files) await import(file);
  } finally {
    process.chdir(cwd);
  }
});
