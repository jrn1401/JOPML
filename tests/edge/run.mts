// Prüft die Edge Function "jopml-ai" mit Attrappen (kein Netz, kein Supabase). Bricht bei jedem Fehler mit Exit-Code 1 ab.
// Die Funktion liest die Nutzer-ID selbst aus dem JWT (Signatur prüft das Supabase-Gateway, verify_jwt = true).
import { state } from "./mock.mjs";

let handler: any;
(globalThis as any).Deno = { env: { get: (k: string) => ({ SUPABASE_URL: "http://x", SUPABASE_ANON_KEY: "a", SUPABASE_SERVICE_ROLE_KEY: "s", GEMINI_API_KEY: "g" } as any)[k] }, serve: (h: any) => { handler = h; } };
const calls: any[] = [];
(globalThis as any).fetch = async (url: string, init: any) => { calls.push({ url, init }); return { ok: true, json: async () => ({ candidates: [{ content: { parts: [{ text: "```\nclick\n```" }] } }] }) }; };
await import("./index.ts");

let failed = 0;
const check = (cond: boolean, what: string) => { console.log(cond ? "  ok  " : "  FAIL", what); if (!cond) failed++; };
const b64u = (o: unknown) => btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const jwt = (payload: unknown) => `${b64u({ alg: "HS256", typ: "JWT" })}.${b64u(payload)}.sig`;
const future = Math.floor(Date.now() / 1000) + 3600;
const GOOD = jwt({ role: "authenticated", sub: "u1", exp: future });

const mk = (token: string | null, body: any, method = "POST") => new Request("http://f", { method, headers: token ? { Authorization: "Bearer " + token } : {}, body: method === "POST" ? JSON.stringify(body) : undefined });
const out = async (r: Response) => [r.status, await r.json()] as [number, any];
const ok = { kind: "macro", lang: "de", messages: [{ role: "user", content: "klick" }] };

check((await out(await handler(mk(null, ok))))[0] === 401, "ohne Anmeldung: 401");
check((await out(await handler(mk("bad", ok))))[0] === 401, "kaputtes Token: 401");
check((await out(await handler(mk(jwt({ role: "anon", exp: future }), ok))))[0] === 401, "anon-Schlüssel statt Nutzer: 401");
check((await out(await handler(mk(jwt({ role: "authenticated", sub: "u1", exp: 1000 }), ok))))[0] === 401, "abgelaufenes Token: 401");
check((await handler(mk(GOOD, ok, "GET"))).status === 405, "GET: 405");
check((await out(await handler(mk(GOOD, { ...ok, kind: "x" }))))[0] === 400, "unbekannte Art: 400");
check((await out(await handler(mk(GOOD, { kind: "help", messages: [{ role: "system", content: "x" }] }))))[0] === 400, "Rolle system: 400");
check((await out(await handler(mk(GOOD, { kind: "help", messages: [{ role: "user", content: "x".repeat(1000) }, { role: "assistant", content: "y".repeat(1000) }, ...Array(6).fill({ role: "user", content: "z".repeat(1000) })] }))))[0] === 400, "zu lang: 400");
check(calls.length === 0 && state.hits === 0, "abgelehnte Anfragen erreichen weder Kontingent noch Gemini");

const [st, res] = await out(await handler(mk(GOOD, ok)));
check(st === 200 && typeof res.reply === "string" && res.reply.includes("click"), "Makro-Antwort");
check(state.last?.p_user === "u1", "Kontingent zählt für den Nutzer aus dem Token");
const sent = JSON.parse(calls[0].init.body);
check(calls[0].init.headers["x-goog-api-key"] === "g" && !calls[0].url.includes("key="), "Gemini-Schlüssel nur im Header");
check(sent.systemInstruction.parts[0].text.includes("repeat forever") && sent.generationConfig.temperature === 0.2, "Makro-Prompt und Temperatur");

const [hs] = await out(await handler(mk(GOOD, { kind: "help", lang: "zh", version: "1.5.3", messages: [{ role: "user", content: "hi" }] })));
const helpSys = JSON.parse(calls[1].init.body).systemInstruction.parts[0].text;
check(hs === 200 && helpSys.includes("Simplified Chinese") && helpSys.includes("v1.5.3"), "Hilfe: Sprache und installierte Version");
check((await out(await handler(mk(GOOD, ok))))[0] === 429, "Tageslimit: 429");

if (failed) { console.error(`${failed} Edge-Prüfung(en) fehlgeschlagen`); process.exit(1); }
console.log("Edge-Function: alle Prüfungen bestanden");
