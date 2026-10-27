import { Client } from "@langchain/langgraph-sdk";

export function createClient() {
  const apiUrl =
    process.env.NEXT_PUBLIC_LANGGRAPH_API_URL ?? "http://127.0.0.1:2024";
  return new Client({ apiUrl });
}
