// Runs the smoke test inside workerd, the Cloudflare Workers runtime, through Miniflare.
import { fileURLToPath } from 'node:url';
import { Miniflare } from 'miniflare';

const worker = new Miniflare({
  modules: true,
  modulesRoot: fileURLToPath(new URL('../..', import.meta.url)),
  scriptPath: fileURLToPath(new URL('./worker.js', import.meta.url)),
  modulesRules: [{ type: 'ESModule', include: ['**/*.js'] }],
  compatibilityDate: '2026-07-01',
});
try {
  const response = await worker.dispatchFetch('http://localhost/');
  const body = await response.text();
  if (!response.ok) throw new Error(body);
  console.log('extralt works on Cloudflare Workers (workerd)');
} finally {
  await worker.dispose();
}
