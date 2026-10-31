import { log } from "./chat_mock.mjs";
let handler: any;
const keys: any = { SUPABASE_URL: "http://x", SUPABASE_SERVICE_ROLE_KEY: "s", GEMINI_API_KEY: "g", GROQ_API_KEY: "q" };
(globalThis as any).Deno = { env: { get: (k: string) => keys[k] }, serve: (h: any) => { handler = h; } };
const jwt = (sub: string) => "x." + Buffer.from(JSON.stringify({ role: "authenticated", sub, exp: 9999999999 })).toString("base64url") + ".y";
const sse = (lines: string[]) => new Response(new ReadableStream({ start(c) { const e = new TextEncoder(); for (const l of lines) c.enqueue(e.encode(l + "\n\n")); c.close(); } }), { status: 200 });
let geminiMode = "ok";
const calls: string[] = [];
(globalThis as any).fetch = async (url: string, init: any) => {
  calls.push(url);
  if (url.includes("generativelanguage") && url.includes("streamGenerateContent")) {
    if (geminiMode === "429") return new Response("quota", { status: 429 });
    return sse([`data: ${JSON.stringify({ candidates: [{ content: { parts: [{ text: "Hal" }] } }] })}`, `data: ${JSON.stringify({ candidates: [{ content: { parts: [{ text: "lo" }] } }], usageMetadata: { totalTokenCount: 42 } })}`]);
  }
  if (url.includes("generativelanguage") && url.includes("generateContent")) {
    if (geminiMode === "429") return new Response("quota", { status: 429 });
    return new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: "Hi" }] } }], usageMetadata: { totalTokenCount: 7 } }));
  }
  if (url.includes("groq.com") && url.endsWith("/models")) return new Response(JSON.stringify({ data: [{ id: "llama-3.3-70b-versatile" }, { id: "whisper-large" }] }));
  if (url.includes("groq.com")) {
    const b = JSON.parse(init.body);
    if (b.stream) return sse([`data: ${JSON.stringify({ choices: [{ delta: { content: "Gr" } }] })}`, `data: ${JSON.stringify({ choices: [{ delta: { content: "oq" } }], x_groq: { usage: { total_tokens: 11 } } })}`, "data: [DONE]"]);
    return new Response(JSON.stringify({ choices: [{ message: { content: "G" } }], usage: { total_tokens: 3 } }));
  }
  return new Response("{}", { status: 404 });
};
await import("./chat_index.ts");
const mk = (body: any) => new Request("http://f", { method: "POST", headers: { Authorization: "Bearer " + jwt("u1") }, body: JSON.stringify(body) });
const m = [{ role: "user", content: "hi" }];
const sBody = async (r: Response) => await r.text();
let r = await handler(mk({ provider: "gemini", messages: m, stream: true }));
let t = await sBody(r);
console.log("stream", r.status, JSON.stringify(t.split("\u001e")[0]), JSON.parse(t.split("\u001eMETA")[1]).tokens, r.headers.get("X-Provider"));
geminiMode = "429";
r = await handler(mk({ provider: "gemini", messages: m, stream: true }));
t = await sBody(r);
const meta = JSON.parse(t.split("\u001eMETA")[1]);
console.log("fallback", JSON.stringify(t.split("\u001e")[0]), meta.provider, meta.fallback_from, meta.fallback_reason, meta.tokens);
r = await handler(mk({ provider: "gemini", messages: m, stream: false }));
const j = await r.json();
console.log("nonstream-fallback", j.reply, j.provider, j.fallback_from);
r = await handler(mk({ provider: "gemini", messages: m, stream: true, fallback: false }));
console.log("nofallback", r.status, (await r.json()).code);
geminiMode = "ok";
r = await handler(mk({ kind: "models" }));
console.log("models", JSON.stringify((await r.json()).models.groq));
console.log("log", log.rpc.filter((x) => x[0] === "jopml_ai_log").map((x) => JSON.stringify(x[1])).join(" | "));
