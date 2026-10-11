// Runs the smoke test on Node.js, Bun or Deno: `<runtime> test/runtime/run.js` after a build.
import { smoke } from './smoke.js';

await smoke();
const runtime = globalThis.Deno
  ? `Deno ${globalThis.Deno.version.deno}`
  : globalThis.Bun
    ? `Bun ${globalThis.Bun.version}`
    : `Node.js ${globalThis.process.version}`;
console.log(`extralt works on ${runtime}`);
