import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL('../../', import.meta.url));
const web = fileURLToPath(new URL('../', import.meta.url));
const env = {
  ...process.env,
  NEXT_PUBLIC_SUPABASE_URL: '',
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: '',
  NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8001',
  NEXT_PUBLIC_LOCAL_PREVIEW: 'true',
};
const children = [
  spawn(`${root}.venv/bin/python`, ['-m', 'uvicorn', 'tee_api.local:app', '--host', '127.0.0.1', '--port', '8001'],
    { cwd: root, env, stdio: 'inherit' }),
  spawn(process.execPath, [require.resolve('next/dist/bin/next'), 'dev', '--hostname', '127.0.0.1', '--port', '3001'],
    { cwd: web, env, stdio: 'inherit' }),
];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
  process.exitCode = code;
}
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop());
for (const child of children) {
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => { if (!stopping) stop(code ?? 1); });
}
console.log('Local preview: http://127.0.0.1:3001 (reads .local/tee-times.json).');
