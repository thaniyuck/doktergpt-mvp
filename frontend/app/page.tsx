"use client";

import { useState } from "react";

import Sidebar from "@/components/sidebar";
import TopBar from "@/components/topbar";
import ChatArea from "@/components/chatarena";
import EvidencePanel from "@/components/evidencepanel";
import ChatInput from "@/components/chatinput";

export default function Home() {
  // What the user is CURRENTLY TYPING (bound to the textarea only)
  const [input, setInput] = useState("");

  // The SUBMITTED question (shown as the user bubble in ChatArea)
  const [query, setQuery] = useState("");

  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<any[]>([]);
  const [latency, setLatency] = useState(0);
  const [loading, setLoading] = useState(false);

  const askDokterGPT = async () => {
    const question = input.trim();

    // Ignore empty sends and double-clicks while a request is in flight
    if (!question || loading) return;

    setQuery(question);      // show the user bubble
    setInput("");            // clear the textarea
    setSources([]);
    setLatency(0);
    setLoading(true);
    setAnswer("Analyzing clinical evidence..."); // visible feedback while waiting

    try {
      const res = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: question }),
      });

      if (!res.ok) {
        throw new Error(`Server responded with status ${res.status}`);
      }

      const data = await res.json();

      setAnswer(data.answer);
      setSources(data.sources);
      setLatency(data.latency);
    } catch (err) {
      setAnswer(
        "⚠️ Could not reach the DokterGPT backend. Make sure the API server is running on http://127.0.0.1:8000 (see run instructions), then try again."
      );
    } finally {
      setLoading(false);
    }
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
        input={input}
        setInput={setInput}
        askDokterGPT={askDokterGPT}
        loading={loading}
      />
    </div>
  );
}
