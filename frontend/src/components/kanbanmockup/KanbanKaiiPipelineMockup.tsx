const appFlowSteps = [
  {
    title: "Sign in",
    description: "User opens KanbanKaii and enters the workspace.",
    badge: "01",
    accent: "from-violet-400 to-fuchsia-400",
  },
  {
    title: "Connect Slack",
    description: "The app is authorized to listen for relevant task messages.",
    badge: "02",
    accent: "from-cyan-300 to-sky-400",
  },
  {
    title: "Message arrives",
    description: "A teammate mentions the user with an actionable request.",
    badge: "03",
    accent: "from-amber-300 to-orange-400",
  },
  {
    title: "Ticket created",
    description: "KanbanKaii turns the message into a clean board card.",
    badge: "04",
    accent: "from-emerald-300 to-teal-400",
  },
];

export function KanbanKaiiPipelineMockup() {
  return (
    <section
      className="relative isolate overflow-hidden rounded-[2rem] border border-violet-100 bg-white/70 p-4 text-slate-950 shadow-[0_30px_100px_-50px_rgba(124,58,237,0.45)] backdrop-blur-xl sm:p-6 lg:p-8"
      aria-label="KanbanKaii app workflow animation mockup"
    >
      <div
        className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-violet-300/45 blur-[90px]"
        aria-hidden="true"
      />
      <div
        className="absolute right-[-8rem] top-1/4 h-80 w-80 rounded-full bg-cyan-200/35 blur-[100px]"
        aria-hidden="true"
      />
      <div
        className="absolute bottom-[-8rem] left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-emerald-200/35 blur-[100px]"
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 bg-[linear-gradient(rgba(109,83,170,0.07)_1px,transparent_1px),linear-gradient(90deg,rgba(109,83,170,0.07)_1px,transparent_1px)] bg-[size:44px_44px]"
        aria-hidden="true"
      />

      <div className="relative mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-violet-600">
            KanbanKaii workflow
          </p>
          <h3 className="mt-2 max-w-xl text-3xl font-black leading-none tracking-[-0.055em] text-slate-950 sm:text-4xl">
            Watch a message become a ticket.
          </h3>
        </div>
      </div>

      <div className="relative grid gap-4 lg:grid-cols-[0.72fr_1.28fr]">
        <div className="rounded-[1.5rem] border border-violet-100 bg-white/76 p-4 shadow-lg shadow-violet-100/40 backdrop-blur-xl sm:p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-violet-500">
                Walkthrough
              </p>
            </div>
            <span className="grid h-9 w-9 place-items-center rounded-2xl bg-violet-500 text-sm font-black shadow-lg shadow-violet-500/30">
              K
            </span>
          </div>

          <div className="space-y-3">
            {appFlowSteps.map((step, index) => (
              <div
                key={step.title}
                className={`kanban-flow-step kanban-flow-step-${index + 1} relative overflow-hidden rounded-2xl border border-violet-100 bg-white/80 p-4 shadow-lg shadow-violet-100/40`}
              >
                <div
                  className={`absolute left-0 top-0 h-full w-1 bg-gradient-to-b ${step.accent}`}
                  aria-hidden="true"
                />
                <div className="flex gap-4">
                  <span
                    className={`grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br ${step.accent} text-xs font-black text-slate-950`}
                  >
                    {step.badge}
                  </span>
                  <div>
                    <h4 className="text-sm font-black text-slate-950">
                      {step.title}
                    </h4>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      {step.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="overflow-hidden rounded-[1.5rem] border border-violet-200/80 bg-violet-50/55 shadow-2xl shadow-violet-200/55 backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-violet-100 bg-violet-100/45 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-300/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/80" />
            </div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-400">
              app_preview.walkthrough
            </p>
          </div>

          <div className="relative min-h-[34rem] overflow-hidden p-4 sm:min-h-[31rem]">
            <SignInScreen />
            <SlackConnectScreen />
            <SlackMessageScreen />
            <TicketCreatedScreen />
          </div>
        </div>
      </div>
    </section>
  );
}

function SignInScreen() {
  return (
    <div className="kanban-walkthrough-screen kanban-walkthrough-screen-1 absolute inset-4 grid place-items-center">
      <div className="w-full max-w-md rounded-[1.7rem] border border-violet-100 bg-white/90 p-5 shadow-2xl shadow-violet-100/60 backdrop-blur-xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-violet-600">
              Step 1
            </p>
            <h4 className="mt-2 text-2xl font-black tracking-[-0.04em] text-slate-950">
              Sign in to KanbanKaii
            </h4>
          </div>
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-violet-500 text-sm font-black shadow-lg shadow-violet-500/30">
            K
          </span>
        </div>
        <div className="space-y-3">
          <div className="rounded-xl border border-violet-100 bg-violet-50/45 px-4 py-3 text-sm text-slate-600">
            example@company.com
          </div>
          <div className="rounded-xl border border-violet-100 bg-violet-50/45 px-4 py-3 text-sm text-slate-400">
            ••••••••••••
          </div>
          <button
            className="kanban-click-bounce mt-2 w-full rounded-xl bg-violet-500 px-4 py-3 text-sm font-black text-white shadow-lg shadow-violet-500/30"
            type="button"
          >
            Sign in
          </button>
        </div>
        <p className="mt-5 text-xs leading-5 text-slate-500">
          The user enters a private dashboard where tickets will appear.
        </p>
      </div>
    </div>
  );
}

function SlackConnectScreen() {
  return (
    <div className="kanban-walkthrough-screen kanban-walkthrough-screen-2 absolute inset-4 grid place-items-center">
      <div className="w-full max-w-lg rounded-[1.7rem] border border-cyan-100 bg-white/90 p-5 shadow-2xl shadow-cyan-100/40 backdrop-blur-xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-600">
              Step 2
            </p>
            <h4 className="mt-2 text-2xl font-black tracking-[-0.04em] text-slate-950">
              Connect Slack workspace
            </h4>
          </div>
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-[10px] font-black text-emerald-700">
            READY
          </span>
        </div>
        <div className="rounded-2xl border border-violet-100 bg-violet-50/45 p-4">
          <div className="flex items-center gap-4">
            <span className="grid h-14 w-14 place-items-center rounded-2xl bg-white text-2xl font-black text-[#4a154b] shadow-sm">
              #
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">Slack</p>
              <p className="text-xs text-slate-500">Product Team workspace</p>
            </div>
          </div>
          <button
            className="kanban-click-bounce mt-5 w-full rounded-xl bg-violet-600 px-4 py-3 text-sm font-black text-white shadow-lg shadow-violet-200/70"
            type="button"
          >
            Connect Slack
          </button>
        </div>
        <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-xs font-bold text-emerald-700">
          Slack connected successfully
        </div>
      </div>
    </div>
  );
}

function SlackMessageScreen() {
  return (
    <div className="kanban-walkthrough-screen kanban-walkthrough-screen-3 absolute inset-4 grid place-items-center">
      <div className="w-full max-w-xl rounded-[1.7rem] border border-amber-100 bg-white/90 p-5 shadow-2xl shadow-amber-100/40 backdrop-blur-xl">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-600">
              Step 3
            </p>
            <h4 className="mt-2 text-2xl font-black tracking-[-0.04em] text-slate-950">
              A task request arrives
            </h4>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-[10px] font-black text-emerald-700">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
            live
          </span>
        </div>
        <div className="kanban-message-bounce rounded-[1.5rem] border border-violet-100 bg-gradient-to-br from-violet-50 to-white p-5 shadow-2xl shadow-violet-100/60">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-amber-300 text-sm font-black text-amber-950">
              AK
            </span>
            <div>
              <p className="text-sm font-black text-slate-950">Aisha</p>
              <p className="text-xs text-slate-500">#product-team · now</p>
            </div>
          </div>
          <p className="text-xl font-bold leading-8 text-slate-700">
            <span className="rounded-lg bg-violet-100 px-2 py-1 text-violet-700">
              @Umer
            </span>{" "}
            can you fix the checkout validation before tomorrow?
          </p>
        </div>
        <div className="mt-4 rounded-xl border border-violet-100 bg-violet-50 px-4 py-3 text-xs font-bold text-violet-700">
          KanbanKaii checks whether the message is actionable.
        </div>
      </div>
    </div>
  );
}

function TicketCreatedScreen() {
  return (
    <div className="kanban-walkthrough-screen kanban-walkthrough-screen-4 absolute inset-4">
      <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[1.7rem] border border-violet-100 bg-[#f7f7fb] p-4 text-slate-950 shadow-2xl shadow-violet-100/60">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-violet-600">
              Step 4
            </p>
            <h4 className="mt-1 text-xl font-black tracking-[-0.04em]">
              Ticket appears on the board
            </h4>
          </div>
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-[10px] font-black text-emerald-700">
            NEW
          </span>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden rounded-2xl sm:grid-cols-3">
          {["Pending", "In Progress", "Completed"].map((column, index) => (
            <div
              key={column}
              className={`min-h-0 overflow-hidden rounded-2xl bg-slate-100 p-3 ${index > 0 ? "hidden sm:block" : ""}`}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-black text-slate-600">
                  {column}
                </span>
                <span className="text-xs text-slate-400">
                  {index === 0 ? "1" : "0"}
                </span>
              </div>
              {index === 0 ? (
                <article className="kanban-ticket-bounce rounded-2xl border border-violet-100 bg-white p-4 shadow-xl shadow-violet-100/70">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="rounded-md bg-rose-50 px-2 py-1 text-[10px] font-black text-rose-600">
                      HIGH
                    </span>
                    <span className="rounded-md border border-slate-200 px-2 py-1 text-[10px] font-bold text-slate-500">
                      Slack
                    </span>
                  </div>
                  <h5 className="text-sm font-black leading-5">
                    Fix checkout validation
                  </h5>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    Resolve the checkout validation issue before tomorrow.
                  </p>
                  <div className="mt-4 rounded-xl bg-violet-50 px-3 py-2 text-[10px] font-black text-violet-700">
                    Assigned to Umer
                  </div>
                </article>
              ) : (
                <div className="h-40 max-h-[70%] rounded-2xl border border-dashed border-slate-200 bg-white/40" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
