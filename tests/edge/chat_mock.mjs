export const log = { rpc: [] };
export function createClient() {
  return {
    rpc: async (name, args) => { log.rpc.push([name, args]); if (name === "jopml_ai_policy") return { data: [{ daily_requests: 60, max_answer: 2048, daily_tokens: 200000, tokens_used: 5 }], error: null }; return { data: null, error: null }; },
    from: () => ({ select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: { user_id: "u1" } }) }) }) }),
  };
}
