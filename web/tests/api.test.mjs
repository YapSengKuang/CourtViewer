import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
let moduleId = 0;
async function client(t, settings) {
  const keys = ['NEXT_PUBLIC_SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'NEXT_PUBLIC_API_URL'];
  const previous = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
    for (const key of keys) {
      if (previous[key] === undefined) delete process.env[key];
      else process.env[key] = previous[key];
    }
  });
  for (const key of keys) {
    if (settings[key] === undefined) delete process.env[key];
    else process.env[key] = settings[key];
  }
  return import(`data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}#${++moduleId}`);
}
const input = { date: '2026-10-30', timeFrom: '08:00', timeTo: '10:00', players: 2, holes: 'any' };
const configured = {
  NEXT_PUBLIC_SUPABASE_URL: 'https://project.supabase.co/',
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test',
};

test('Supabase mode uses bounded RPC arguments and public key', async t => {
  const api = await client(t, configured);
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'https://project.supabase.co/rest/v1/rpc/golf_search_v2');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.apikey, 'sb_publishable_test');
    assert.equal(options.headers.Authorization, undefined);
    assert.deepEqual(JSON.parse(options.body), {
      p_date: input.date, p_time_from: '08:00', p_time_to: '10:00', p_players: 2,
      p_holes: null, p_limit: 100, p_offset: 0, p_sort: 'starts_at', p_course_slug: null,
    });
    assert.ok(options.signal instanceof AbortSignal);
    return Response.json({ tee_times: [{ course_slug: 'mandalay' }] });
  };
  assert.deepEqual(await api.searchTeeTimes(input), [{ course_slug: 'mandalay' }]);
});

test('incomplete Supabase configuration cannot fall back to localhost', async t => {
  const api = await client(t, { NEXT_PUBLIC_SUPABASE_URL: configured.NEXT_PUBLIC_SUPABASE_URL });
  globalThis.fetch = () => { throw new Error('must not fetch'); };
  await assert.rejects(api.searchTeeTimes(input), /configuration is incomplete/);
});

test('health uses RPC and provider errors remain generic', async t => {
  const api = await client(t, configured);
  globalThis.fetch = async url => {
    assert.ok(url.endsWith('/golf_health'));
    return Response.json({ courses: [] });
  };
  assert.deepEqual(await api.fetchHealth(), []);
  globalThis.fetch = async () => new Response('internal database details', { status: 500 });
  await assert.rejects(api.searchTeeTimes(input), /^Error: Search service unavailable$/);
});

test('local development retains the FastAPI contract', async t => {
  const api = await client(t, { NEXT_PUBLIC_API_URL: 'http://localhost:8000' });
  globalThis.fetch = async url => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, '/api/tee-times');
    assert.equal(parsed.searchParams.get('holes'), '9');
    assert.equal(parsed.searchParams.get('players'), '2');
    return Response.json({ tee_times: [] });
  };
  assert.deepEqual(await api.searchTeeTimes({ ...input, holes: '9' }), []);
});


test('beta search forwards submitted course, sort and page', async t => {
  const api = await client(t, configured);
  globalThis.fetch = async (url, options) => {
    assert.ok(url.endsWith('/golf_search_v2'));
    const args = JSON.parse(options.body);
    assert.equal(args.p_course_slug, 'morack');
    assert.equal(args.p_sort, 'price');
    assert.equal(args.p_offset, 100);
    assert.equal(args.p_limit, 100);
    return Response.json({ tee_times: [], has_more: true, coverage: [{ slug: 'morack', status: 'incomplete' }] });
  };
  const result = await api.searchAvailability({ ...input, courseSlug: 'morack', sort: 'price', offset: 100 });
  assert.equal(result.has_more, true);
  assert.equal(result.coverage[0].status, 'incomplete');
});

test('course picker uses bounded public course metadata RPC', async t => {
  const api = await client(t, configured);
  globalThis.fetch = async url => {
    assert.ok(url.endsWith('/golf_courses'));
    return Response.json({ courses: [{ slug: 'morack', date_to: '2026-10-30' }] });
  };
  assert.equal((await api.fetchCourses())[0].date_to, '2026-10-30');
});
