import ArrowRight from "lucide-react/dist/esm/icons/arrow-right";
import Check from "lucide-react/dist/esm/icons/check";

import { KanbanKaiiPipelineMockup } from "@/components/kanbanmockup/KanbanKaiiPipelineMockup";

const features = [
  {
    number: "01",
    title: "Connect your workspace",
    description:
      "Link Slack from Settings with a secure, account-specific OAuth connection.",
  },
  {
    number: "02",
    title: "Let AI find the work",
    description:
      "Local AI separates actionable requests from questions, chatter, and empty mentions.",
  },
  {
    number: "03",
    title: "Move work forward",
    description:
      "Tickets arrive in real time, ready to edit, prioritize, assign, and drag across your board.",
  },
];

export function LandingPage() {
  const workspaceHref = "/auth?mode=signup";
  const workspaceLabel = "Start for free";

  return (
    <main className="landing-scroll landing-original relative isolate h-screen overflow-y-auto overflow-x-hidden bg-[#f7f7fb] text-slate-950">
      <LandingGradientPatches />

      <div className="relative overflow-hidden">
        <div
          className="landing-grid absolute inset-0 opacity-55"
          aria-hidden="true"
        />
        <div
          className="absolute -left-32 top-24 h-80 w-80 rounded-full bg-violet-300/30 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="absolute -right-24 top-0 h-96 w-96 rounded-full bg-indigo-200/50 blur-3xl"
          aria-hidden="true"
        />

        <nav className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-10">
          <a
            href="/"
            className="flex items-center gap-3"
            aria-label="KanbanKaii home"
          >
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-600 text-sm font-semibold text-white shadow-lg shadow-violet-300/50">
              K
            </span>
            <span className="text-lg font-bold tracking-tight">KanbanKaii</span>
          </a>

          <div className="hidden items-center gap-8 text-sm font-medium text-slate-600 md:flex">
            <a
              className="transition hover:text-violet-700"
              href="#how-it-works"
            >
              How it works
            </a>
            <a className="transition hover:text-violet-700" href="#features">
              Features
            </a>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3">
            <a
              className="rounded-lg px-2.5 py-2 text-xs font-semibold text-slate-700 transition hover:bg-white/70 hover:text-violet-700 sm:px-3 sm:text-sm"
              href="/auth"
            >
              Sign in
            </a>
            <a
              className="inline-flex items-center gap-1.5 rounded-xl bg-slate-950 px-3 py-2.5 text-xs font-semibold text-white shadow-lg shadow-slate-300 transition hover:-translate-y-0.5 hover:bg-violet-700 sm:gap-2 sm:px-4 sm:text-sm"
              href={workspaceHref}
            >
              {workspaceLabel}
              <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </nav>

        <section className="relative z-[1] mx-auto max-w-7xl px-5 pb-14 pt-10 sm:px-8 sm:pt-12 lg:px-10 lg:pb-16 lg:pt-10">
          <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(20rem,0.95fr)] lg:gap-4">
            <div className="relative z-10 max-w-4xl">
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white/80 px-3.5 py-2 text-xs font-bold uppercase tracking-[0.16em] text-violet-700 shadow-sm backdrop-blur">
                Conversation into action
              </div>
              <h1 className="text-5xl font-semibold leading-[0.98] tracking-[-0.035em] text-slate-950 sm:text-6xl lg:text-[5rem] xl:text-[5.65rem]">
                Your messages already know what needs to be done.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg sm:leading-8">
                KanbanKaii spots actionable work in Slack, structures it with
                AI, and places it on your private board - without turning every
                conversation into a ticket.
              </p>
              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <a
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-6 py-3.5 text-sm font-bold text-white shadow-xl shadow-violet-300/40 transition hover:-translate-y-0.5 hover:bg-violet-700"
                  href={workspaceHref}
                >
                  {workspaceLabel}
                  <ArrowRight className="h-4 w-4" />
                </a>
                <a
                  className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white/80 px-6 py-3.5 text-sm font-bold text-slate-700 transition hover:border-violet-200 hover:text-violet-700"
                  href="#how-it-works"
                >
                  See how it works
                </a>
              </div>
              <div className="mt-7 flex flex-wrap gap-x-6 gap-y-3 text-xs font-medium text-slate-500">
                {[
                  "Private by default",
                  "Realtime tickets",
                  "Human editable",
                ].map((item) => (
                  <span key={item} className="inline-flex items-center gap-2">
                    <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-100 text-emerald-700">
                      <Check className="h-3 w-3" />
                    </span>
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="relative mx-auto hidden min-h-[29rem] w-full max-w-[34rem] md:block lg:mx-0 lg:min-h-[35rem] lg:max-w-none">
              <div
                className="absolute inset-x-0 top-10 mx-auto h-[24rem] w-[24rem] rounded-full bg-violet-300/25 blur-3xl lg:h-[30rem] lg:w-[30rem]"
                aria-hidden="true"
              />
              <img
                src="/landing-mobile-showcase.png"
                alt="KanbanKaii mobile dashboard with Slack, analytics, and organization workspace cards"
                className="relative z-10 mx-auto w-[min(78vw,29rem)] select-none drop-shadow-[0_2rem_4rem_rgba(79,70,229,0.18)] lg:mr-[-1.5rem] lg:w-[37rem] xl:mr-[-2.5rem] xl:w-[41rem]"
                draggable="false"
              />
            </div>
          </div>
        </section>
      </div>

      <section
        id="how-it-works"
        className="relative z-10 overflow-hidden bg-transparent px-5 pb-16 pt-24 text-slate-950 sm:px-8 lg:px-10"
      >
        <div
          className="landing-grid absolute inset-0 opacity-45"
          aria-hidden="true"
        />
        <div
          className="absolute -left-32 top-10 h-96 w-96 rounded-full bg-violet-300/45 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="absolute right-0 bottom-0 h-96 w-96 rounded-full bg-indigo-200/45 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative z-10 mx-auto max-w-7xl">
          <div className="grid gap-10 lg:grid-cols-[0.7fr_1.3fr] lg:items-end">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">
                How it works
              </p>
              <h2 className="mt-4 text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">
                Less copying. More doing.
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-slate-500 lg:justify-self-end">
              Keep talking where work happens. KanbanKaii handles the repetitive
              part between a request being made and a useful ticket appearing.
            </p>
          </div>
          <div className="mt-14">
            <KanbanKaiiPipelineMockup />
          </div>
          <div id="features" className="mt-14 grid gap-3 overflow-hidden rounded-[2rem] border border-violet-100 bg-white/55 p-3 shadow-xl shadow-violet-100/40 backdrop-blur-xl md:grid-cols-3">
            {features.map((feature) => (
              <article
                key={feature.number}
                className="rounded-[1.5rem] bg-white/78 p-7 shadow-sm shadow-violet-100/50 transition hover:-translate-y-0.5 hover:bg-white sm:p-9"
              >
                <span className="text-xs font-semibold text-violet-400">
                  {feature.number}
                </span>
                <h3 className="mt-12 text-xl font-bold text-slate-950">
                  {feature.title}
                </h3>
                <p className="mt-3 text-sm leading-6 text-slate-500">
                  {feature.description}
                </p>
              </article>
            ))}
          </div>
        </div>

        <div
          className="absolute inset-x-0 top-1/2 h-96 -translate-y-1/2 bg-gradient-to-r from-violet-200/55 via-white/20 to-indigo-100/60"
          aria-hidden="true"
        />
        <div
          className="absolute left-[-10rem] top-1/2 h-[32rem] w-[32rem] rounded-full bg-violet-300/35 blur-[100px]"
          aria-hidden="true"
        />
        <div
          className="absolute right-[-12rem] bottom-[-12rem] h-[34rem] w-[34rem] rounded-full bg-indigo-200/40 blur-[110px]"
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 bg-[radial-gradient(circle_at_14%_52%,rgba(124,58,237,0.18),transparent_34%),radial-gradient(circle_at_86%_80%,rgba(79,70,229,0.14),transparent_36%)]"
          aria-hidden="true"
        />

        <div className="relative z-10 mx-auto mt-24 grid max-w-7xl gap-10 border-t border-violet-100 pt-24 lg:grid-cols-[0.75fr_1.25fr] lg:items-center">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">
              Ready when you are
            </p>
            <h2 className="mt-4 max-w-2xl text-5xl font-semibold leading-[0.98] tracking-[-0.035em] sm:text-6xl">
              Give every real request somewhere to go.
            </h2>
          </div>
          <div className="max-w-2xl lg:justify-self-end">
            <p className="text-sm leading-7 text-slate-500 sm:text-base sm:leading-8">
              Connect Slack, keep your conversations natural, and let your
              private board collect the work worth doing.
            </p>
            <a
              className="mt-8 inline-flex items-center gap-2 rounded-xl bg-violet-600 px-6 py-3.5 text-sm font-bold text-white shadow-xl shadow-violet-200/70 transition hover:-translate-y-0.5 hover:bg-violet-700"
              href={workspaceHref}
            >
              {workspaceLabel}
              <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      </section>

      <footer className="relative z-10 overflow-hidden border-t border-violet-100 bg-white/45 px-5 py-8 backdrop-blur-xl sm:px-8 lg:px-10">
        <div
          className="landing-grid absolute inset-0 opacity-30"
          aria-hidden="true"
        />
        <div
          className="absolute right-10 bottom-[-8rem] h-72 w-72 rounded-full bg-violet-300/40 blur-3xl"
          aria-hidden="true"
        />
        <div className="mx-auto flex max-w-7xl flex-col gap-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span className="font-bold text-slate-700">KanbanKaii</span>
          <span>Private AI-assisted ticket management.</span>
        </div>
      </footer>
    </main>
  );
}

function LandingGradientPatches() {
  return (
    <div
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      aria-hidden="true"
    >
      <div className="absolute left-[-10rem] top-[8rem] h-[28rem] w-[28rem] rounded-full bg-violet-300/45 blur-[90px]" />
      <div className="absolute right-[-12rem] top-[32rem] h-[26rem] w-[26rem] rounded-full bg-indigo-300/35 blur-[85px]" />
      <div className="absolute left-[18%] bottom-[18%] h-[22rem] w-[22rem] rounded-full bg-fuchsia-200/35 blur-[90px]" />
      <div className="absolute right-[-9rem] bottom-[-4rem] h-[28rem] w-[28rem] rounded-full bg-violet-300/38 blur-[100px]" />
    </div>
  );
}
