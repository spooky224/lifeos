"use client";

import { useEffect, useState } from "react";
import { getGoals, Goal } from "@/lib/api";
import Sidebar from "@/components/Sidebar";

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getGoals()
      .then(setGoals)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <Sidebar />

      <main className="ml-64 p-8">
        <div className="mb-8">
          <p className="text-sm font-medium text-blue-400">LIFEOS</p>
          <h1 className="mt-1 text-3xl font-bold">Goals</h1>
          <p className="mt-2 text-zinc-400">
            Your long-term objectives and current priorities.
          </p>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-zinc-400">
            Loading goals...
          </div>
        ) : goals.length === 0 ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
            <p className="text-lg font-medium">No goals yet</p>
            <p className="mt-2 text-sm text-zinc-500">
              Your goals will appear here when LIFEOS creates them.
            </p>
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {goals.map((goal) => (
              <div
                key={goal.id}
                className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 transition hover:border-zinc-700"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold">{goal.title}</h2>

                    {goal.description && (
                      <p className="mt-2 text-sm leading-6 text-zinc-400">
                        {goal.description}
                      </p>
                    )}
                  </div>

                  <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400">
                    {goal.status}
                  </span>
                </div>

                <div className="mt-6 flex items-center justify-between border-t border-zinc-800 pt-4">
                  <span className="text-xs uppercase tracking-wide text-zinc-500">
                    Priority
                  </span>

                  <span className="text-sm font-medium capitalize text-zinc-300">
                    {goal.priority}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}