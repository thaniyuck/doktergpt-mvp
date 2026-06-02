// frontend/components/EvidencePanel.tsx

interface Source {
  title: string;
  doi: string;
  score: number;
  trust_tier: number;
  study_design: string;
  publication_date: string;
}

interface EvidencePanelProps {
  sources: Source[];
  latency: number;
}

export default function EvidencePanel({
  sources,
  latency,
}: EvidencePanelProps) {
  return (
    <aside className="w-[360px] bg-surface-container border-l border-slate-700 flex flex-col">
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-bold text-[var(--on-surface)]">Evidence Citations</h2>

          <span className="text-cyan-400 text-sm">
            {sources.length} Sources
          </span>
        </div>

        <p className="text-sm text-slate-400">
          Validated via Biomedical VectorDB
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {sources.length === 0 ? (
          <div className="text-slate-500 text-sm">
            No citations available.
          </div>
        ) : (
          sources.map((source, index) => (
            <div
              key={index}
              className="glass-panel rounded-lg p-4 text-[var(--on-surface)]"
            >
              <div className="flex justify-between mb-2">
                <span className="text-cyan-400 text-sm font-bold">
                  [{index + 1}] Evidence
                </span>

                <span className="text-slate-400 text-sm">
                  Score: {(source.score * 100).toFixed(1)}%
                </span>
              </div>

              <h3 className="font-semibold mb-3">
                {source.title}
              </h3>

              <div className="flex flex-wrap gap-2 mb-3">

                <span className="px-2 py-1 rounded text-xs bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  Tier {source.trust_tier}
                </span>

                <span className="px-2 py-1 rounded text-xs bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  {source.study_design}
                </span>

              </div>

              <p className="text-xs text-slate-400 mb-1">
                Published: {source.publication_date}
              </p>

              <p className="text-xs text-slate-400">
                DOI: {source.doi}
              </p>
            </div>
          ))
        )}
      </div>

      <div className="p-4 border-t border-slate-700">
        <div className="bg-slate-800 p-4 rounded">
          <p className="text-xs text-slate-400 uppercase">
            Retrieval Latency
          </p>

          <div className="text-cyan-400 text-2xl font-bold">
            {latency}s
          </div>
        </div>
      </div>
    </aside>
  );
}