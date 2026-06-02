// frontend/components/ChatArea.tsx

interface ChatAreaProps {
  query: string;
  answer: string;
}

export default function ChatArea({
  query,
  answer,
}: ChatAreaProps) {
  return (
    <section className="flex-1 flex flex-col bg-background overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full p-8 space-y-8">

        {query && (
          <div className="flex justify-end">
            <div
              className="
                bg-[var(--surface-variant)]
                text-[var(--on-surface)]
                border
                border-[var(--outline-variant)]
                p-4
                rounded-xl
                rounded-tr-none
                max-w-[80%]
              "
            >
              {query}
            </div>
          </div>
        )}

        {answer && (
          <div className="flex justify-start">
            <div className="glass-panel p-6 rounded-xl max-w-[85%] text-[var(--on-surface)]">
              <div className="mb-2 font-bold text-cyan-400">
                DokterGPT Analyst
              </div>

              <p className="text-[var(--on-surface)]"
              >{answer}
              </p>
            </div>
          </div>
        )}

      </div>
    </section>
  );
}