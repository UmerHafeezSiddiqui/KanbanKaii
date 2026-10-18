import type { TicketPriority } from '@/types/ticket';

const priorityColors: Record<TicketPriority, string> = {
  High: 'bg-rose-500',
  Medium: 'bg-amber-500',
  Low: 'bg-emerald-500',
};

const weekdayFormatter = new Intl.DateTimeFormat(undefined, { weekday: 'short' });

export type WeeklyActivityDay = {
  count: number;
  date: Date;
  key: string;
};

export type PriorityDistributionItem = {
  count: number;
  percentage: number;
  priority: TicketPriority;
};

export type AnalyticsChartsProps = {
  maximumDailyCount: number;
  priorityDistribution: PriorityDistributionItem[];
  ticketCount: number;
  weeklyActivity: WeeklyActivityDay[];
};

export function AnalyticsCharts({
  maximumDailyCount,
  priorityDistribution,
  ticketCount,
  weeklyActivity,
}: AnalyticsChartsProps) {
  return (
    <section className="mt-5 grid gap-5 lg:grid-cols-[1.5fr_1fr]">
      <TicketsCreatedChart maximumDailyCount={maximumDailyCount} weeklyActivity={weeklyActivity} />
      <PriorityDistributionChart priorityDistribution={priorityDistribution} ticketCount={ticketCount} />
    </section>
  );
}

function TicketsCreatedChart({
  maximumDailyCount,
  weeklyActivity,
}: Pick<AnalyticsChartsProps, 'maximumDailyCount' | 'weeklyActivity'>) {
  const safeMax = Math.max(1, maximumDailyCount);

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-800">Tickets created</h2>
      <p className="mt-1 text-xs text-slate-400">New tickets during the last seven days</p>
      <div
        className="mt-8 flex h-52 items-end justify-between gap-3 border-b border-slate-100 px-2"
        role="figure"
        aria-label="Weekly tickets created activity chart"
      >
        {weeklyActivity.map((day) => {
          const height = day.count ? Math.max(10, Math.min(100, (day.count / safeMax) * 100)) : 2;
          const weekdayLabel = weekdayFormatter.format(day.date);
          return (
            <div
              key={day.key}
              className="flex h-full flex-1 flex-col items-center justify-end gap-2"
              title={`${day.count} ticket${day.count === 1 ? '' : 's'}`}
            >
              <span className="text-[10px] font-medium text-slate-500">{day.count}</span>
              <div
                className="w-full max-w-10 rounded-t bg-violet-500/80 transition-all"
                style={{ height: `${height}%` }}
                aria-hidden="true"
              />
              <span className="text-[10px] text-slate-400">{weekdayLabel}</span>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function PriorityDistributionChart({
  priorityDistribution,
  ticketCount,
}: Pick<AnalyticsChartsProps, 'priorityDistribution' | 'ticketCount'>) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-800">Priority distribution</h2>
      <p className="mt-1 text-xs text-slate-400">All tickets by priority</p>
      <div className="mt-6 space-y-5">
        {priorityDistribution.map(({ priority, count, percentage }) => (
          <div key={priority}>
            <div className="mb-2 flex justify-between text-xs">
              <span className="font-medium text-slate-600">{priority}</span>
              <span className="text-slate-400">{count} · {percentage}%</span>
            </div>
            <div
              className="h-2 overflow-hidden rounded-full bg-slate-100"
              role="progressbar"
              aria-label={`${priority} priority percentage`}
              aria-valuenow={percentage}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className={`h-full rounded-full transition-all ${priorityColors[priority]}`}
                style={{ width: `${percentage}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      {ticketCount === 0 && (
        <p className="mt-8 text-center text-xs text-slate-400">Create a ticket to begin seeing analytics.</p>
      )}
    </article>
  );
}
