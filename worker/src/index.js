// Search API over the mathematicians' full text.
//   GET /search?q=...&k=10&author=tao&year_min=1990&year_max=2020
//   Authorization: Bearer <SEARCH_TOKEN>
// Queries are embedded with Workers AI bge-base-en-v1.5 using CLS pooling, matching
// the offline sentence-transformers embeddings (checked by `msp parity-check`).
// The endpoint returns snippets of copyrighted papers, so it always requires a token.

export const MODEL = "@cf/baai/bge-base-en-v1.5";
export const QUERY_PREFIX = "Represent this sentence for searching relevant passages: ";
const MAX_K = 50; // Vectorize topK cap when returning metadata

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

async function authorized(request, token) {
  if (!token) return false; // fail closed if the secret was never set
  const given = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(given)),
    crypto.subtle.digest("SHA-256", enc.encode(token)),
  ]);
  const x = new Uint8Array(a), y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i]; // constant time
  return diff === 0;
}

export function buildFilter(params) {
  const filter = {};
  const author = params.get("author");
  if (author) filter.author = { $eq: author };
  const lo = Number(params.get("year_min")), hi = Number(params.get("year_max"));
  if (params.has("year_min") && Number.isFinite(lo)) filter.year = { ...filter.year, $gte: lo };
  if (params.has("year_max") && Number.isFinite(hi)) filter.year = { ...filter.year, $lte: hi };
  return Object.keys(filter).length ? filter : undefined;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") return json({ ok: true });
    if (url.pathname !== "/search") return json({ error: "not found" }, 404);
    if (request.method !== "GET") return json({ error: "use GET" }, 405);
    if (!(await authorized(request, env.SEARCH_TOKEN))) return json({ error: "unauthorized" }, 401);

    const q = (url.searchParams.get("q") || "").trim();
    if (!q) return json({ error: "missing q" }, 400);
    if (q.length > 2000) return json({ error: "q too long" }, 400);
    const k = Math.min(Math.max(parseInt(url.searchParams.get("k") || "10", 10) || 10, 1), MAX_K);

    const emb = await env.AI.run(MODEL, { text: [QUERY_PREFIX + q], pooling: "cls" });
    const vector = emb.data[0];
    const opts = { topK: k, returnMetadata: "all" };
    const filter = buildFilter(url.searchParams);
    if (filter) opts.filter = filter;
    const res = await env.VECTORIZE.query(vector, opts);
    return json({
      query: q,
      k,
      filter: filter || null,
      matches: (res.matches || []).map((m) => ({ score: Number(m.score.toFixed(4)), ...m.metadata })),
    });
  },
};
