"use client";

import { FormEvent, useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import {
  activateRoutine,
  createRoutine,
  deactivateRoutine,
  deleteRoutine,
  getRoutines,
  Routine,
} from "@/lib/api";

const days = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" },
];

export default function RoutinesPage() {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [frequency, setFrequency] = useState("daily");
  const [duration, setDuration] = useState(30);
  const [preferredTime, setPreferredTime] = useState("");
  const [priority, setPriority] = useState("medium");
  const [selectedDays, setSelectedDays] = useState<number[]>([]);

  useEffect(() => {
    getRoutines()
      .then(setRoutines)
      .finally(() => setLoading(false));
  }, []);

  function toggleDay(day: number) {
    setSelectedDays((current) =>
      current.includes(day)
        ? current.filter((value) => value !== day)
        : [...current, day]
    );
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();

    if (!name.trim()) {
      return;
    }

    setCreating(true);

    try {
      const routine = await createRoutine({
        name: name.trim(),
        description: null,
        frequency,
        days_of_week:
          frequency === "weekly" ? selectedDays : null,
        preferred_time: preferredTime || null,
        duration_minutes: duration,
        priority,
        goal_id: null,
      });

      setRoutines((current) => [routine, ...current]);

      setName("");
      setPreferredTime("");
      setSelectedDays([]);
    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Failed to create routine."
      );
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(routine: Routine) {
    try {
      const result = routine.is_active
        ? await deactivateRoutine(routine.id)
        : await activateRoutine(routine.id);

      setRoutines((current) =>
        current.map((item) =>
          item.id === routine.id
            ? { ...item, is_active: result.is_active }
            : item
        )
      );
    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Failed to update routine."
      );
    }
  }

  async function handleDelete(routineId: number) {
    if (!confirm("Delete this routine?")) {
      return;
    }

    try {
      await deleteRoutine(routineId);

      setRoutines((current) =>
        current.filter((routine) => routine.id !== routineId)
      );
    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Failed to delete routine."
      );
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <Sidebar />

      <main className="ml-64 p-8">
        <div className="mb-8">
          <p className="text-sm font-medium text-blue-400">
            LIFEOS
          </p>

          <h1 className="mt-1 text-3xl font-bold">
            Routines
          </h1>

          <p className="mt-2 text-zinc-400">
            Recurring activities LIFEOS should keep track of.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
          <form
            onSubmit={handleCreate}
            className="h-fit rounded-2xl border border-zinc-800 bg-zinc-900 p-6"
          >
            <h2 className="text-lg font-semibold">
              Create Routine
            </h2>

            <div className="mt-5 space-y-4">
              <div>
                <label className="text-sm text-zinc-400">
                  Name
                </label>

                <input
                  value={name}
                  onChange={(event) =>
                    setName(event.target.value)
                  }
                  placeholder="Study AI"
                  className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-sm text-zinc-400">
                  Frequency
                </label>

                <select
                  value={frequency}
                  onChange={(event) =>
                    setFrequency(event.target.value)
                  }
                  className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>

              {frequency === "weekly" && (
                <div>
                  <label className="text-sm text-zinc-400">
                    Days
                  </label>

                  <div className="mt-2 flex flex-wrap gap-2">
                    {days.map((day) => {
                      const selected =
                        selectedDays.includes(day.value);

                      return (
                        <button
                          type="button"
                          key={day.value}
                          onClick={() =>
                            toggleDay(day.value)
                          }
                          className={`rounded-lg px-3 py-2 text-xs font-medium ${
                            selected
                              ? "bg-blue-600 text-white"
                              : "bg-zinc-800 text-zinc-400"
                          }`}
                        >
                          {day.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <div>
                <label className="text-sm text-zinc-400">
                  Duration (minutes)
                </label>

                <input
                  type="number"
                  min="1"
                  value={duration}
                  onChange={(event) =>
                    setDuration(Number(event.target.value))
                  }
                  className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2"
                />
              </div>

              <div>
                <label className="text-sm text-zinc-400">
                  Preferred time
                </label>

                <input
                  type="time"
                  value={preferredTime}
                  onChange={(event) =>
                    setPreferredTime(event.target.value)
                  }
                  className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2"
                />
              </div>

              <div>
                <label className="text-sm text-zinc-400">
                  Priority
                </label>

                <select
                  value={priority}
                  onChange={(event) =>
                    setPriority(event.target.value)
                  }
                  className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={creating}
                className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium transition hover:bg-blue-500 disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create Routine"}
              </button>
            </div>
          </form>

          <section>
            {loading ? (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-zinc-400">
                Loading routines...
              </div>
            ) : routines.length === 0 ? (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
                <p className="font-medium">
                  No routines yet
                </p>

                <p className="mt-2 text-sm text-zinc-500">
                  Create your first recurring activity.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {routines.map((routine) => (
                  <div
                    key={routine.id}
                    className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-3">
                          <h2 className="font-semibold">
                            {routine.name}
                          </h2>

                          <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300">
                            {routine.frequency}
                          </span>

                          <span
                            className={`rounded-full px-3 py-1 text-xs ${
                              routine.is_active
                                ? "bg-green-950 text-green-300"
                                : "bg-zinc-800 text-zinc-500"
                            }`}
                          >
                            {routine.is_active
                              ? "Active"
                              : "Inactive"}
                          </span>
                        </div>

                        <p className="mt-2 text-sm text-zinc-400">
                          {routine.duration_minutes} min
                          {routine.preferred_time
                            ? ` · ${routine.preferred_time.slice(
                                0,
                                5
                              )}`
                            : ""}
                          {" · "}
                          {routine.priority} priority
                        </p>
                      </div>

                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            toggleActive(routine)
                          }
                          className="rounded-lg bg-zinc-800 px-4 py-2 text-sm hover:bg-zinc-700"
                        >
                          {routine.is_active
                            ? "Deactivate"
                            : "Activate"}
                        </button>

                        <button
                          onClick={() =>
                            handleDelete(routine.id)
                          }
                          className="rounded-lg bg-zinc-800 px-4 py-2 text-sm text-red-400 hover:bg-zinc-700"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}