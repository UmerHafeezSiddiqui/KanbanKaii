export function AuthBrandPanel() {
  return (
    <section className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-violet-600 via-violet-600 to-indigo-700 p-10 text-white lg:flex">
      <div
        className="absolute -left-20 top-12 h-72 w-72 rounded-full bg-white/15 blur-3xl"
        aria-hidden="true"
      />
      <div
        className="absolute right-[-7rem] bottom-[-7rem] h-80 w-80 rounded-full bg-indigo-300/20 blur-3xl"
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] bg-[size:52px_52px] opacity-30"
        aria-hidden="true"
      />

      <div className="relative z-10">
        <div className="mb-12 inline-flex rounded-full border border-white/20 bg-white/15 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-violet-50 backdrop-blur">
          AI Ticket Board
        </div>
        <h1 className="max-w-md text-4xl font-black leading-tight tracking-[-0.045em]">
          Turn conversations into organized work.
        </h1>
        <p className="mt-5 max-w-md text-sm leading-6 text-violet-100/90">
          Capture actionable messages, prioritize them with local AI, and manage
          every task from one private Kanban board.
        </p>
      </div>
      <div className="relative z-10 rounded-2xl border border-white/15 bg-white/10 p-4 text-xs text-violet-50 backdrop-blur">
        <p className="font-bold">Private workspace</p>
        <p className="mt-1 text-violet-100/80">
          Slack-ready · Realtime tickets
        </p>
      </div>
    </section>
  );
}
