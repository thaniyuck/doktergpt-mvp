"use client";

import { useState } from "react";

import Sidebar from "@/components/sidebar";
import TopBar from "@/components/topbar";
import ChatArea from "@/components/chatarena";
import EvidencePanel from "@/components/evidencepanel";
import ChatInput from "@/components/chatinput";

export default function Home() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<any[]>([]);
  const [latency, setLatency] = useState(0);

  const askDokterGPT = async () => {
    const res = await fetch(
      "http://127.0.0.1:8000/ask",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      }
    );

    const data = await res.json();

    setAnswer(data.answer);
    setSources(data.sources);
    setLatency(data.latency);
  };

  return (
    <div className="bg-background text-on-surface">
      <Sidebar />
      <TopBar />

      <main className="ml-[280px] pt-16 h-screen flex overflow-hidden">
        <ChatArea 
        query={query}
        answer={answer} 
        />

        <EvidencePanel
          sources={sources}
          latency={latency}
        />
      </main>

      <ChatInput
        query={query}
        setQuery={setQuery}
        askDokterGPT={askDokterGPT}
      />
    </div>
  );
}