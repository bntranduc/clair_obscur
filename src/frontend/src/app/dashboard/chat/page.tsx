import type { Metadata } from "next";
import AgenticChatAssistant from "@/components/dashboard/AgenticChatAssistant";

export const metadata: Metadata = {
  title: "Assistant IA — CLAIR OBSCUR",
  description: "Assistant agentic en flux SSE (réflexion, outils, mémoire par session).",
};

export default function ChatPage() {
  return (
    <div className="flex min-h-0 min-w-0 w-full flex-1 flex-col overflow-hidden">
      <AgenticChatAssistant />
    </div>
  );
}
