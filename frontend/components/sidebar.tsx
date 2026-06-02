export default function Sidebar() {
  return (
    <>
    <aside className="fixed left-0 top-0 h-full w-[280px] bg-[var(--surface-container-low)] border-r border-[var(--outline-variant)] backdrop-blur-xl flex flex-col py-8 px-4 z-50">
    <div className="mb-8 px-4">
    <h1 className="text-headline-md font-headline-md font-bold text-[var(--primary)]">DokterGPT</h1>
    <p className="text-label-sm font-label-sm text-[var(--on-surface-variant)]">Biomedical RAG Engine</p>
    </div>
    <nav className="flex-1 space-y-2">
    <a className="flex items-center gap-3 px-4 py-3 text-[var(--on-surface-variant)] hover:text-[var(--on-surface)] hover:bg-surface-variant/50 transition-colors duration-200 rounded-lg group" href="#">
    <span className="material-symbols-outlined">dashboard</span>
    <span className="text-label-md font-label-md">Dashboard</span>
    </a>
    <a className="flex items-center gap-3 px-4 py-3 text-[var(--primary)] font-bold border-r-2 border-primary bg-[#89ceff]/10 rounded-lg scale-[0.98] transition-all duration-200" href="#">
    <span className="material-symbols-outlined">chat_bubble</span>
    <span className="text-label-md font-label-md">Chat</span>
    </a>
    <a className="flex items-center gap-3 px-4 py-3 text-[var(--on-surface-variant)] hover:text-[var(--on-surface)] hover:bg-surface-variant/50 transition-colors duration-200 rounded-lg" href="#">
    <span className="material-symbols-outlined">database</span>
    <span className="text-label-md font-label-md">Database</span>
    </a>
    <a className="flex items-center gap-3 px-4 py-3 text-[var(--on-surface-variant)] hover:text-[var(--on-surface)] hover:bg-surface-variant/50 transition-colors duration-200 rounded-lg" href="#">
    <span className="material-symbols-outlined">analytics</span>
    <span className="text-label-md font-label-md">Analytics</span>
    </a>
    </nav>
    <div className="mt-auto space-y-4 px-4">
    <button className="w-full py-3 bg-[var(--primary)] text-on-primary font-label-md text-label-md rounded-lg flex items-center justify-center gap-2 hover:brightness-110 transition-all">
    <span className="material-symbols-outlined text-[18px]">download</span>
                    Export DB JSON
                </button>
    <a className="flex items-center gap-3 py-3 text-[var(--on-surface-variant)] hover:text-[var(--on-surface)] transition-colors" href="#">
    <span className="material-symbols-outlined">settings</span>
    <span className="text-label-md font-label-md">Settings</span>
    </a>
    <div className="flex items-center gap-3 pt-4 border-t border-[var(--outline-variant)]">
    <div className="w-10 h-10 rounded-full overflow-hidden bg-surface-variant">
    <img alt="Chief Medical Officer" className="w-full h-full object-cover" data-alt="A highly detailed professional portrait of a senior medical researcher in a modern, clinical environment. The lighting is bright and clean, characteristic of a high-end laboratory. The doctor wears a minimalist white coat over a dark navy shirt, reflecting a sophisticated, authoritative medical persona. The background is softly blurred, showing hints of advanced medical equipment and high-tech digital displays." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAb5jGxc8Q1G5wBaVaMDzi1_tm2AFKpkNUINajLgl7idX-88ipDknan_ctBLp3N7Q3T4EXQKFXeo5UlfblCInunay6PvP3NmNoytNRjhWSMIo2_QmgJOBAgesxFSoZ44v0SaZWeNPN7HIHfwcVEkhKrdTS7rwk42r7jXJqKPJ2XTFPr9fCxHq2BDeEgvzJ5gwpDo2Zs-udmzN9xT7CYW4T9JzgMiCocH8cAbuKq29E_Pd-oXgS59KaIBqj_3b8TApneP6TjpYmgRppW"/>
    </div>
    <div className="flex flex-col">
    <span className="text-label-md font-label-md font-bold text-[var(--on-surface)]">Dr. Aris AI</span>
    <span className="text-label-sm font-label-sm text-[var(--on-surface-variant)]">Chief Med Officer</span>
    </div>
    </div>
    </div>
    </aside>
    </>
  );
}