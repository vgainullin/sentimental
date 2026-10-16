// Run with: cd worker && npm test
import assert from "node:assert/strict";
import test from "node:test";
import worker, { buildFilter, MODEL, QUERY_PREFIX } from "../src/index.js";

function env(calls) {
  return {
    SEARCH_TOKEN: "s3cret",
    AI: { run: async (model, input) => { calls.ai = { model, input }; return { data: [[0.1, 0.2]] }; } },
    VECTORIZE: {
      query: async (vector, opts) => {
        calls.vec = { vector, opts };
        return { matches: [{ id: "x", score: 0.912345, metadata: { title: "T", author: "tao" } }] };
      },
    },
  };
}
const req = (path, token = "s3cret") =>
  new Request(`https://w.example${path}`, { headers: token ? { authorization: `Bearer ${token}` } : {} });

test("health needs no token", async () => {
  const r = await worker.fetch(req("/health", null), env({}));
  assert.equal(r.status, 200);
});

test("search rejects missing or wrong token, and fails closed without a secret", async () => {
  assert.equal((await worker.fetch(req("/search?q=x", null), env({}))).status, 401);
  assert.equal((await worker.fetch(req("/search?q=x", "nope"), env({}))).status, 401);
  const e = env({}); delete e.SEARCH_TOKEN;
  assert.equal((await worker.fetch(req("/search?q=x"), e)).status, 401);
});

test("search embeds with CLS pooling and the BGE query prefix", async () => {
  const calls = {};
  const r = await worker.fetch(req("/search?q=sieve%20weights&k=500&author=tao&year_min=2000"), env(calls));
  assert.equal(r.status, 200);
  assert.equal(calls.ai.model, MODEL);
  assert.deepEqual(calls.ai.input, { text: [QUERY_PREFIX + "sieve weights"], pooling: "cls" });
  assert.equal(calls.vec.opts.topK, 50); // clamped
  assert.deepEqual(calls.vec.opts.filter, { author: { $eq: "tao" }, year: { $gte: 2000 } });
  const body = await r.json();
  assert.equal(body.matches[0].score, 0.9123);
  assert.equal(body.matches[0].author, "tao");
});

test("filters", () => {
  assert.equal(buildFilter(new URLSearchParams("")), undefined);
  assert.deepEqual(buildFilter(new URLSearchParams("year_min=1900&year_max=1950")),
    { year: { $gte: 1900, $lte: 1950 } });
  assert.equal(buildFilter(new URLSearchParams("year_min=abc")), undefined);
});

test("bad requests", async () => {
  assert.equal((await worker.fetch(req("/search"), env({}))).status, 400);
  assert.equal((await worker.fetch(req("/nope"), env({}))).status, 404);
});
