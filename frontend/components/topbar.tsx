export default function TopBar() {
  return (
    <>
    <header
      className="fixed top-0 right-0 w-[calc(100%-280px)] h-16 backdrop-blur-md z-40"
      style={{
        backgroundColor: "rgba(11,19,38,0.8)",
        borderBottom: "1px solid var(--outline-variant)",
      }}
    >
    <div className="flex justify-between items-center px-gutter h-full">
    <div className="flex items-center gap-8">
    <span className="font-bold text-[var(--primary)]">
      Chat Arena
    </span>

    <nav className="hidden md:flex items-center gap-6">
      <a
        className="text-[var(--on-surface-variant)] hover:text-[var(--primary)] transition-colors"
        href="#"
      >
        Explorer
      </a>

      <a
        className="text-[var(--secondary)] font-medium"
        href="#"
      >
        Ollama: Active
      </a>

      <a
        className="text-[var(--on-surface-variant)]"
        href="#"
      >
        VectorDB: Ready
      </a>
    </nav>
    </div>
    <div className="flex items-center gap-4">
    <button className="p-2 text-[var(--on-surface-variant)] hover:text-[var(--primary)]">
    <span className="material-symbols-outlined">notifications</span>
    </button>
    <div className="h-8 w-8 rounded-full bg-surface-variant border border-outline-variant overflow-hidden">
    <img alt="User Profile" className="w-full h-full object-cover" data-alt="A close-up, high-detail digital avatar of a clinical investigator, characterized by a clean-cut, professional appearance in a dark mode UI environment. The character has focused, intelligent eyes and wears a subtle, technical-looking headset. The lighting features a cool blue rim light that matches the clinical teal and slate color palette of the DokterGPT system." src="https://lh3.googleusercontent.com/aida-public/AB6AXuBJV7qTluDFN2gOWygb8ExP2AlI9J19yLtbd_m9uN_TApFr8ytF59PZPdWAQmqRkw17AmVlSUwImk7MJyLaoPiA_s9H3LJvrTH24hb8IyW4ka-H3GajbsAZeoWk5jrzw6GBStbBDfNvppnxKZHvw4yDv7X19HXPov15Wu5UzIjLRIL040jVNC-a5e0dwhBYX4LaUTzj0UQMyDd9lHwXIfAaP_9qnLOFoZ8iTMBnGiQCuaURatb8Lj931nGbo_3h6VbNshJ7tFe-WvnT"/>
    </div>
    </div>
    </div>
    </header>
    </>
  );
}