import type { Metadata } from "next";
import AgenticChatAssistant from "@/components/dashboard/AgenticChatAssistant";

export const metadata: Metadata = {
  title: "Assistant IA — CLAIR OBSCUR",
  description: "Assistant agentic en flux SSE (réflexion, outils, mémoire par session).",
};

export default function ChatPage() {
  return <AgenticChatAssistant />;
}
