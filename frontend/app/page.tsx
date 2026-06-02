"use client";

import { useState } from "react";

export default function Home() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<any[]>([]);
  const [latency, setLatency] = useState(0);

  const askDokterGPT = async () => {
    try {
      const res = await fetch(
        "http://127.0.0.1:8000/ask",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query,
          }),
        }
      );

      const data = await res.json();

      setAnswer(data.answer);
      setSources(data.sources);
      setLatency(data.latency);
    } catch {
      setAnswer("Backend unavailable.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <h1 className="text-3xl font-bold mb-6">
        DokterGPT MVP
      </h1>

      <textarea
        className="w-full border p-4 rounded text-black"
        rows={4}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <button
        onClick={askDokterGPT}
        className="mt-4 px-4 py-2 bg-blue-600 rounded"
      >
        Ask
      </button>

      <div className="mt-8">
        <h2 className="font-bold">Answer</h2>
        <p>{answer}</p>
      </div>

      <div className="mt-8">
        <h2 className="font-bold">
          Latency: {latency}s
        </h2>
      </div>

      <div className="mt-8">
        <h2 className="font-bold">Sources</h2>

        {sources.map((s, i) => (
          <div
            key={i}
            className="border p-3 my-2 rounded"
          >
            <p>{s.title}</p>
            <p>{s.doi}</p>
            <p>{s.score}</p>
          </div>
        ))}
      </div>
    </div>
  );
}