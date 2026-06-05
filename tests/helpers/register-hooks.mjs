// Registers the absolute-import resolve hook for the test run.
// Wired into `npm test` via `node --import`.
import { register } from 'node:module';

register('./absolute-import-hooks.mjs', import.meta.url);
