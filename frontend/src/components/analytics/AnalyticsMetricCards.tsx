export type AnalyticsMetric = {
  detail: string;
  label: string;
  value: number;
};

export type AnalyticsMetricCardsProps = {
  metrics: AnalyticsMetric[];
};

export function AnalyticsMetricCards({ metrics }: AnalyticsMetricCardsProps) {
  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Summary metrics">
      {metrics.map((metric) => (
        <article
          key={metric.label}
          className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
        >
          <p className="text-xs font-medium text-slate-500">{metric.label}</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{metric.value}</p>
          <p className="mt-2 text-[11px] font-medium text-violet-600">{metric.detail}</p>
        </article>
      ))}
    </section>
  );
}
