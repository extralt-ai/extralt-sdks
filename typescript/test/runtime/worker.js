// A Cloudflare Worker that runs the smoke test; loaded by workers.js in workerd.
import { smoke } from './smoke.js';

export default {
  async fetch() {
    try {
      await smoke();
      return new Response('ok');
    } catch (error) {
      return new Response(String(error?.stack ?? error), { status: 500 });
    }
  },
};
