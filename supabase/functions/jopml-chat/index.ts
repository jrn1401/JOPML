// Supabase Edge Function "jopml-chat" (v3, Update 1.10.0): KI-Chat mit Gemini (Google) und Groq, Streaming, automatischer Wechsel bei Ausfall/Limit des Anbieters.
// Die Schlüssel liegen NUR hier als Secrets – nie im Launcher:
//   GEMINI_API_KEY, GROQ_API_KEY
// Optional: GEMINI_MODEL, GROQ_MODEL (Standardmodelle), AI_CHAT_USER_LIMIT (Rückfall, falls keine Datenbankregel), AI_GLOBAL_LIMIT.
// Streaming: body.stream=true liefert Text-Stücke; am Ende "\u001eMETA{json}" (Anbieter, Modell, Tokens, Wechsel). Vor dem ersten Text ist ein Wechsel auf den anderen Anbieter möglich.
// Arten (kind): "status" (Anbieter, Standardmodelle, eigene Limits), "models" (Modellliste je Anbieter),
//               "analyze" (nur Admins: Fehlergruppen auswerten), sonst Chat.
// Regeln für Antwortlänge/Tokens kommen aus der Datenbank (Admin-Bereich): -1 = kein Limit.
import { createClient } from "npm:@supabase/supabase-js@2";

const DEFAULTS: Record<string, string> = {
  gemini: Deno.env.get("GEMINI_MODEL") ?? "gemini-3.5-flash-lite",
  groq: Deno.env.get("GROQ_MODEL") ?? "llama-3.3-70b-versatile",
};
const KEYS: Record<string, string> = { gemini: "GEMINI_API_KEY", groq: "GROQ_API_KEY" };
const USER_LIMIT = Number(Deno.env.get("AI_CHAT_USER_LIMIT") ?? 100);
const GLOBAL_LIMIT = Number(Deno.env.get("AI_GLOBAL_LIMIT") ?? 2000);
const HARD_MAX = 16384;               // technische Obergrenze auch bei "kein Limit"
const LANGS: Record<string, string> = { en: "English", de: "German", es: "Spanish", ru: "Russian", fr: "French", zh: "Simplified Chinese" };
const MODEL_RE = /^[A-Za-z0-9._:\/-]{2,80}$/;

const json = (obj: unknown, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
const fail = (code: string, error: string, status: number) => json({ error, code }, status);

function jwtUser(token: string): string | null {
  try {
    const p = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (p.role !== "authenticated" || typeof p.sub !== "string") return null;
    if (typeof p.exp === "number" && p.exp * 1000 < Date.now()) return null;
    return p.sub;
  } catch { return null; }
}

const configured = () => Object.keys(KEYS).filter((p) => !!Deno.env.get(KEYS[p]));

// ---- Modellliste (10 Minuten Zwischenspeicher), bei Fehlern nur das Standardmodell
const cache: Record<string, { at: number; list: string[] }> = {};
const SKIP = /(embed|tts|image|imagen|veo|aqa|whisper|guard|playai|orpheus|transcri|speech|audio|live|robotics|vision-preview)/i;
async function listModels(p: string): Promise<string[]> {
  const hit = cache[p];
  if (hit && Date.now() - hit.at < 600_000) return hit.list;
  let list: string[] = [];
  try {
    const key = Deno.env.get(KEYS[p])!;
    if (p === "gemini") {
      const r = await fetch("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", { headers: { "x-goog-api-key": key } });
      if (r.ok) {
        const d = await r.json();
        list = (d.models ?? []).filter((m: any) => (m.supportedGenerationMethods ?? []).includes("generateContent"))
          .map((m: any) => String(m.name).replace(/^models\//, ""));
      }
    } else {
      const r = await fetch("https://api.groq.com/openai/v1/models", { headers: { Authorization: `Bearer ${key}` } });
      if (r.ok) list = ((await r.json()).data ?? []).filter((m: any) => m.active !== false).map((m: any) => String(m.id));
    }
  } catch (e) { console.error("models", p, String(e).slice(0, 200)); }
  list = list.filter((m) => MODEL_RE.test(m) && !SKIP.test(m)).sort();
  if (!list.includes(DEFAULTS[p])) list.unshift(DEFAULTS[p]);
  cache[p] = { at: Date.now(), list };
  return list;
}

async function pickModel(p: string, want: unknown): Promise<string> {
  if (typeof want !== "string" || !MODEL_RE.test(want)) return DEFAULTS[p];
  return (await listModels(p)).includes(want) ? want : DEFAULTS[p];
}

function system(lang: string, context: string): string {
  return `You are an AI assistant inside "Jaron's OP Makro Launcher". Be accurate, helpful and honest; say when you are unsure. Reply in ${LANGS[lang] ?? "English"} unless the user writes in another language.
You are an AI system; never pretend to be a human. Keep answers as short as the question allows.
Do not help with cheating in online/multiplayer games (aimbots, wallhacks, recoil compensation, memory reading, anti-cheat bypass), with malware, or with unlawful content. Single-player tools, productivity macros and practice programs are fine.
When you write code, macros or modules, say briefly that the user must review it before running it.${context ? "\n\nCONTEXT (requirements and facts to follow):\n" + context : ""}`;
}

type Msg = { role: "user" | "assistant"; content: string };
type Out = { text: string; tokens: number };

async function callProvider(p: string, model: string, msgs: Msg[], sys: string, maxTokens: number): Promise<Out> {
  const key = Deno.env.get(KEYS[p])!;
  if (p === "groq") {
    const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify({ model, max_tokens: maxTokens, temperature: 0.6, messages: [{ role: "system", content: sys }, ...msgs] }),
    });
    if (!r.ok) throw new Error(`groq ${r.status} ${(await r.text()).slice(0, 200)}`);
    const d = await r.json();
    return { text: String(d?.choices?.[0]?.message?.content ?? "").trim(), tokens: Number(d?.usage?.total_tokens ?? 0) };
  }
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": key },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: sys }] },
      contents: msgs.map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] })),
      generationConfig: { temperature: 0.7, maxOutputTokens: maxTokens },
    }),
  });
  if (!r.ok) throw new Error(`gemini ${r.status} ${(await r.text()).slice(0, 200)}`);
  const d = await r.json();
  return {
    text: (d?.candidates?.[0]?.content?.parts ?? []).map((x: any) => x.text ?? "").join("").trim(),
    tokens: Number(d?.usageMetadata?.totalTokenCount ?? 0),
  };
}

// ---- Streaming-Aufruf: liefert den ersten Textteil sofort (Fehler davor -> Wechsel auf den anderen Anbieter möglich)
type Ev = { text?: string; tokens?: number };
type Opened = { first: string; rest: AsyncGenerator<Ev>; cancel: () => void; tokens: number };

async function openStream(p: string, model: string, msgs: Msg[], sys: string, maxTokens: number): Promise<Opened> {
  const key = Deno.env.get(KEYS[p])!;
  let r: Response;
  if (p === "groq") {
    r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify({ model, max_tokens: maxTokens, temperature: 0.6, stream: true, stream_options: { include_usage: true },
        messages: [{ role: "system", content: sys }, ...msgs] }),
    });
  } else {
    r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?alt=sse`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: sys }] },
        contents: msgs.map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] })),
        generationConfig: { temperature: 0.7, maxOutputTokens: maxTokens },
      }),
    });
  }
  if (!r.ok || !r.body) throw new Error(`${p} ${r.status} ${(await r.text()).slice(0, 200)}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  const state = { tokens: 0 };
  async function* events(): AsyncGenerator<Ev> {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i: number;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (!data || data === "[DONE]") continue;
        let d: any;
        try { d = JSON.parse(data); } catch { continue; }
        if (p === "groq") {
          const t = d?.choices?.[0]?.delta?.content;
          const u = d?.usage?.total_tokens ?? d?.x_groq?.usage?.total_tokens;
          if (u) state.tokens = Number(u);
          if (t) yield { text: String(t) };
        } else {
          const t = (d?.candidates?.[0]?.content?.parts ?? []).map((x: any) => x.text ?? "").join("");
          const u = d?.usageMetadata?.totalTokenCount;
          if (u) state.tokens = Number(u);
          if (t) yield { text: t };
        }
      }
    }
  }
  const gen = events();
  const first = await gen.next();                      // wirft bei Verbindungsfehlern, bevor der Nutzer etwas sieht
  if (first.done || !first.value?.text) { try { await reader.cancel(); } catch { /* */ } throw new Error(`${p} empty`); }
  return { first: first.value.text, rest: gen, cancel: () => { try { reader.cancel(); } catch { /* */ } }, get tokens() { return state.tokens; } } as Opened;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
  const userId = token ? jwtUser(token) : null;
  if (!userId) return fail("not_signed_in", "Not signed in.", 401);

  let body: any;
  try { body = await req.json(); } catch { return fail("bad_request", "Invalid request.", 400); }
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const avail = configured();

  async function policy() {
    const { data } = await admin.rpc("jopml_ai_policy", { p_user: userId });
    const row = Array.isArray(data) ? data[0] : data;
    return {
      daily_requests: Number(row?.daily_requests ?? USER_LIMIT), max_answer: Number(row?.max_answer ?? 2048),
      daily_tokens: Number(row?.daily_tokens ?? 200000), tokens_used: Number(row?.tokens_used ?? 0),
    };
  }
  async function account(provider: string, model: string, tokens: number, fallback: boolean) {
    try {
      if (tokens > 0) await admin.rpc("jopml_ai_add_tokens", { p_user: userId, p_tokens: tokens });
      await admin.rpc("jopml_ai_log", { p_provider: provider, p_model: model, p_tokens: tokens, p_fallback: fallback });
    } catch (e) { console.error("account", String(e).slice(0, 200)); }
  }

  if (body?.kind === "status") return json({ providers: avail, models: DEFAULTS, policy: await policy() });
  if (body?.kind === "models") {
    const out: Record<string, string[]> = {};
    for (const p of avail) out[p] = await listModels(p);
    return json({ providers: avail, models: out, defaults: DEFAULTS });
  }

  const raw = Array.isArray(body?.messages) ? body.messages.slice(-12) : [];
  const msgs: Msg[] = [];
  let total = 0;
  for (const m of raw) {
    if (!m || (m.role !== "user" && m.role !== "assistant") || typeof m.content !== "string") return fail("bad_request", "Invalid request.", 400);
    const text = m.content.slice(0, 4000);
    total += text.length;
    msgs.push({ role: m.role, content: text });
  }
  if (!msgs.length || msgs[msgs.length - 1].role !== "user" || total > 16000) return fail("bad_request", "Invalid request.", 400);
  const lang = typeof body.lang === "string" ? body.lang : "en";
  let context = typeof body.context === "string" ? body.context.slice(0, 14000) : "";

  if (body?.kind === "analyze") {
    const { data: adm } = await admin.from("jopml_admins").select("user_id").eq("user_id", userId).maybeSingle();
    if (!adm) return fail("forbidden", "Not allowed.", 403);
    context = "Task: analyse these aggregated error reports from a desktop app (Python/CustomTkinter). For each group give: likely cause, concrete fix, priority (high/medium/low). Then list the 3 most important actions. Be concise.\n" + context;
  }

  if (!avail.length) return fail("not_configured", "The AI chat is not set up yet (no provider key on the server).", 503);
  const want = typeof body?.provider === "string" ? body.provider : "gemini";
  const first = (want === "groq" ? "groq" : "gemini");
  if (!avail.includes(first) && body?.fallback === false) return fail("provider_missing", "This AI is not set up on the server.", 503);
  // Reihenfolge: gewählter Anbieter, danach (wenn erlaubt) der andere. Ist der gewählte nicht eingerichtet, übernimmt der andere mit Hinweis.
  const other = first === "gemini" ? "groq" : "gemini";
  const order = [first, ...(body?.fallback === false ? [] : [other])].filter((p) => avail.includes(p));

  const { error: rerr } = await admin.rpc("jopml_ai_hit", { p_user: userId, p_user_limit: USER_LIMIT, p_global_limit: GLOBAL_LIMIT });
  if (rerr) {
    const m = String(rerr.message);
    if (m.includes("token_limited")) return fail("limit_tokens", "Daily token limit reached. Please try again tomorrow.", 429);
    if (m.includes("rate_limited_global")) return fail("limit_global", "The AI budget of the day is used up. Please try again tomorrow.", 429);
    if (m.includes("rate_limited")) return fail("limit_requests", "Daily AI limit reached. Please try again tomorrow.", 429);
    return fail("server", "Server error.", 500);
  }
  const pol = await policy();
  let maxTokens = pol.max_answer < 0 ? HARD_MAX : Math.min(Math.max(pol.max_answer, 64), HARD_MAX);
  if (typeof body.max_tokens === "number" && body.max_tokens > 0) maxTokens = Math.min(maxTokens, Math.floor(body.max_tokens));

  const sys = system(lang, context);
  const inChars = sys.length + total;
  const reasons: string[] = [];
  for (const p of order) {
    const model = p === first ? await pickModel(p, body.model) : DEFAULTS[p];
    const fellBack = p !== first || !avail.includes(first);
    const meta = { provider: p, model, max_answer: maxTokens, ai_generated: true, fallback_from: fellBack ? first : null, fallback_reason: fellBack ? (reasons[0] ?? "not_configured") : null };
    try {
      if (body.stream === true) {
        const o = await openStream(p, model, msgs, sys, maxTokens);
        const enc = new TextEncoder();
        let out = o.first.length, done = false;
        const finish = async () => {
          if (done) return; done = true;
          const t = o.tokens || Math.ceil((inChars + out) / 4);
          await account(p, model, t, fellBack);
          return t;
        };
        const stream = new ReadableStream({
          async start(c) {
            c.enqueue(enc.encode(o.first));
            try { for await (const ev of o.rest) { if (ev.text) { out += ev.text.length; c.enqueue(enc.encode(ev.text)); } } } catch (e) { console.error("stream", String(e).slice(0, 200)); }
            const t = await finish();
            c.enqueue(enc.encode("\u001eMETA" + JSON.stringify({ ...meta, tokens: t })));
            c.close();
          },
          async cancel() { o.cancel(); await finish(); },
        });
        return new Response(stream, { headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "X-Provider": p, "X-Model": model, "X-Fallback-From": fellBack ? first : "" } });
      }
      const res = await callProvider(p, model, msgs, sys, maxTokens);
      if (res.text) {
        await account(p, model, res.tokens || Math.ceil((inChars + res.text.length) / 4), fellBack);
        return json({ reply: res.text, tokens: res.tokens, ...meta });
      }
      reasons.push("empty");
    } catch (e) {
      const msg = String(e);
      console.error("chat", msg.slice(0, 300));
      reasons.push(/ 429 |quota|rate/i.test(msg) ? "limit" : "error");
    }
  }
  return fail("provider_down", "The AI service is not available right now.", 502);
});
