"use client";

import { useMemo, useSyncExternalStore } from "react";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { unstable_createLangGraphStream, useLangGraphRuntime, type LangChainMessage } from "@assistant-ui/react-langgraph";
import { createClient } from "@/lib/chatApi";
import { threads } from "@/lib/threads";
import { ChatThread } from "./ChatThread";

export function FeiAssistant({ module = "general", onNavigate }: { module?: "general" | "job_search"; onNavigate?: (target: string) => void }) {
  const client = useMemo(() => createClient(), []);
  const store = useSyncExternalStore(threads.subscribe, threads.snapshot, threads.snapshot);
  const assistantId = module === "job_search" ? "fei-job-search" : "fei-assistant";
  const stream = useMemo(() => unstable_createLangGraphStream({ client, assistantId }), [client, assistantId]);
  const runtime = useLangGraphRuntime({
    unstable_allowCancellation: true,
    stream,
    threadId: store.active ?? undefined,
    onThreadIdChange: (id) => {
      if (id) threads.touch(id);
    },
    create: async () => ({ externalId: (await client.threads.create()).thread_id }),
    load: async (externalId) => {
      const state = await client.threads.getState<{ messages: LangChainMessage[] }>(externalId);
      return { messages: state.values.messages ?? [], interrupts: state.tasks[0]?.interrupts };
    },
  });
  return <AssistantRuntimeProvider runtime={runtime}><ChatThread module={module} onNavigate={onNavigate} /></AssistantRuntimeProvider>;
}
