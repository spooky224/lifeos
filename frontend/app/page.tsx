import Sidebar from "@/components/Sidebar";
import {
  getCalendarEvents,
  getGoals,
  getTasks,
} from "@/lib/api";

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export default async function Dashboard() {
  const [goals, tasks, events] = await Promise.all([
    getGoals(),
    getTasks(),
    getCalendarEvents(),
  ]);

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <Sidebar />

      <main className="ml-64 min-h-screen p-10">
        <div className="mx-auto max-w-7xl">
          <header className="mb-10">
            <p className="text-sm text-zinc-500">Personal command center</p>

            <h2 className="mt-2 text-4xl font-semibold tracking-tight">
              Good afternoon.
            </h2>

            <p className="mt-3 max-w-2xl text-zinc-400">
              LIFEOS coordinates your goals, tasks, schedule, and decisions in
              one place.
            </p>
          </header>

          <section className="grid gap-4 md:grid-cols-3">
            <StatCard
              label="Active Goals"
              value={goals.length}
              description="Goals currently in your system"
            />

            <StatCard
              label="Tasks"
              value={tasks.length}
              description="Tasks connected to your goals"
            />

            <StatCard
              label="Scheduled"
              value={events.length}
              description="Upcoming calendar events"
            />
          </section>

          <section className="mt-10 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6">
              <div className="mb-6">
                <h3 className="text-lg font-semibold">Upcoming schedule</h3>
                <p className="mt-1 text-sm text-zinc-500">
                  Events currently persisted by LIFEOS
                </p>
              </div>

              <div className="space-y-3">
                {events.length === 0 ? (
                  <p className="text-sm text-zinc-500">
                    No upcoming events.
                  </p>
                ) : (
                  events.map((event) => (
                    <div
                      key={event.id}
                      className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-950 p-4"
                    >
                      <div>
                        <p className="font-medium">{event.title}</p>
                        <p className="mt-1 text-sm text-zinc-500">
                          {formatDate(event.start_time)}
                        </p>
                      </div>

                      <div className="text-right">
                        <p className="text-sm font-medium">
                          {formatTime(event.start_time)}
                        </p>
                        <p className="text-xs text-zinc-500">
                          → {formatTime(event.end_time)}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6">
              <h3 className="text-lg font-semibold">Goals</h3>

              <div className="mt-6 space-y-4">
                {goals.map((goal) => (
                  <div
                    key={goal.id}
                    className="rounded-xl border border-zinc-800 bg-zinc-950 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-medium">{goal.name}</p>

                      <span className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-400">
                        {goal.priority}
                      </span>
                    </div>

                    <p className="mt-2 text-xs text-zinc-500">
                      {goal.status}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6">
            <div className="mb-6">
              <h3 className="text-lg font-semibold">Tasks</h3>
              <p className="mt-1 text-sm text-zinc-500">
                Current work connected to your goals
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="rounded-xl border border-zinc-800 bg-zinc-950 p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium">{task.title}</p>
                      <p className="mt-2 text-sm text-zinc-500">
                        {task.estimated_duration_minutes} minutes
                      </p>
                    </div>

                    <span className="rounded-full border border-zinc-800 px-3 py-1 text-xs text-zinc-400">
                      {task.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-6 rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-900 to-zinc-950 p-8">
            <p className="text-sm text-zinc-500">LIFEOS AI</p>

            <h3 className="mt-2 text-2xl font-semibold">
              What should we plan?
            </h3>

            <p className="mt-2 text-sm text-zinc-500">
              Tell LIFEOS what you want to accomplish and let the agents
              coordinate the next steps.
            </p>

            <a
              href="/chat"
              className="mt-6 inline-flex rounded-xl bg-white px-5 py-3 text-sm font-medium text-black transition hover:bg-zinc-200"
            >
              Open AI Chat →
            </a>
          </section>
        </div>
      </main>
    </div>
  );
}

function StatCard({
  label,
  value,
  description,
}: {
  label: string;
  value: number;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6">
      <p className="text-sm text-zinc-500">{label}</p>

      <p className="mt-3 text-4xl font-semibold">{value}</p>

      <p className="mt-2 text-xs text-zinc-600">{description}</p>
    </div>
  );
}
