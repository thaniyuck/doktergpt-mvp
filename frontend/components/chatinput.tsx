// frontend/components/ChatInput.tsx

interface ChatInputProps {
  query: string;
  setQuery: (value: string) => void;
  askDokterGPT: () => void;
}

export default function ChatInput({
  query,
  setQuery,
  askDokterGPT,
}: ChatInputProps) {
  return (
    <div className="fixed bottom-0 left-[280px] right-[360px] p-6 bg-background border-t border-slate-700">
      <div className="max-w-4xl mx-auto flex gap-3">

        <textarea
          value={query}
          onChange={(e) =>
            setQuery(e.target.value)
          }
          rows={2}
          placeholder="Describe symptoms, clinical data, or ask for research evidence..."
          className="flex-1
          bg-[var(--surface-container)]
          text-[var(--on-surface)]
          border border-[var(--outline-variant)]
          rounded-xl
          p-4
          resize-none"
        />

        <button
          onClick={askDokterGPT}
          className="px-5 bg-sky-500 rounded-xl hover:bg-sky-400 transition"
        >
          Send
        </button>

      </div>
    </div>
  );
}