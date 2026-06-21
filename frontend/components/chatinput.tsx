// frontend/components/ChatInput.tsx

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  askDokterGPT: () => void;
  loading: boolean;
}

export default function ChatInput({
  input,
  setInput,
  askDokterGPT,
  loading,
}: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends the message; Shift+Enter makes a new line
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askDokterGPT();
    }
  };

  return (
    <div className="fixed bottom-0 left-[280px] right-[360px] p-6 bg-background border-t border-slate-700">
      <div className="max-w-4xl mx-auto flex gap-3">

        <textarea
          value={input}
          onChange={(e) =>
            setInput(e.target.value)
          }
          onKeyDown={handleKeyDown}
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
          disabled={loading}
          className="px-5 bg-sky-500 rounded-xl hover:bg-sky-400 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "..." : "Send"}
        </button>

      </div>
    </div>
  );
}
