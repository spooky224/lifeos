"use client";

import { useEffect, useState } from "react";
import {
  getTasks,
  updateTaskStatus,
  Task,
  TaskStatus,
} from "@/lib/api";
import Sidebar from "@/components/Sidebar";

const statusLabels: Record<TaskStatus, string> = {
  planned: "Planned",
  scheduled: "Scheduled",
  in_progress: "In Progress",
  completed: "Completed",
  postponed: "Postponed",
  missed: "Missed",
  cancelled: "Cancelled",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingTaskId, setUpdatingTaskId] = useState<number | null>(null);

  useEffect(() => {
    getTasks()
      .then(setTasks)
      .finally(() => setLoading(false));
  }, []);

  async function changeStatus(
    taskId: number,
    status: TaskStatus
  ) {
    setUpdatingTaskId(taskId);

    try {
      const updatedTask = await updateTaskStatus(taskId, status);

      setTasks((currentTasks) =>
        currentTasks.map((task) =>
          task.id === taskId ? updatedTask : task
        )
      );
    } catch (error) {
      console.error(error);
      alert(
        error instanceof Error
          ? error.message
          : "Failed to update task status."
      );
    } finally {
      setUpdatingTaskId(null);
    }
  }

  function getActions(task: Task) {
    switch (task.status as TaskStatus) {
      case "planned":
        return [
          {
            label: "Schedule",
            status: "scheduled" as TaskStatus,
          },
          {
            label: "Cancel",
            status: "cancelled" as TaskStatus,
          },
        ];

      case "scheduled":
        return [
          {
            label: "Start",
            status: "in_progress" as TaskStatus,
          },
          {
            label: "Postpone",
            status: "postponed" as TaskStatus,
          },
          {
            label: "Missed",
            status: "missed" as TaskStatus,
          },
          {
            label: "Cancel",
            status: "cancelled" as TaskStatus,
          },
        ];

      case "in_progress":
        return [
          {
            label: "Complete",
            status: "completed" as TaskStatus,
          },
          {
            label: "Postpone",
            status: "postponed" as TaskStatus,
          },
          {
            label: "Cancel",
            status: "cancelled" as TaskStatus,
          },
        ];

      case "postponed":
      case "missed":
        return [
          {
            label: "Schedule Again",
            status: "scheduled" as TaskStatus,
          },
          {
            label: "Cancel",
            status: "cancelled" as TaskStatus,
          },
        ];

      case "completed":
      case "cancelled":
        return [];

      default:
        return [];
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <Sidebar />

      <main className="ml-64 p-8">
        <div className="mb-8">
          <p className="text-sm font-medium text-blue-400">LIFEOS</p>

          <h1 className="mt-1 text-3xl font-bold">
            Tasks
          </h1>

          <p className="mt-2 text-zinc-400">
            Concrete actions generated from your goals.
          </p>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-zinc-400">
            Loading tasks...
          </div>
        ) : tasks.length === 0 ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
            <p className="text-lg font-medium">
              No tasks yet
            </p>

            <p className="mt-2 text-sm text-zinc-500">
              Tasks created by LIFEOS will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {tasks.map((task) => {
              const actions = getActions(task);
              const isUpdating = updatingTaskId === task.id;

              return (
                <div
                  key={task.id}
                  className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5 transition hover:border-zinc-700"
                >
                  <div className="flex flex-col gap-5">
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-3">
                          <h2 className="font-semibold">
                            {task.title}
                          </h2>

                          <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300">
                            {statusLabels[task.status as TaskStatus] ??
                              task.status}
                          </span>

                          <span className="rounded-full bg-blue-950 px-3 py-1 text-xs text-blue-300">
                            {task.priority}
                          </span>
                        </div>

                        {task.description && (
                          <p className="mt-2 text-sm text-zinc-400">
                            {task.description}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-6 text-sm">
                        <div>
                          <p className="text-xs uppercase tracking-wide text-zinc-500">
                            Duration
                          </p>

                          <p className="mt-1 font-medium text-zinc-300">
                            {task.estimated_duration_minutes} min
                          </p>
                        </div>

                        {task.deadline && (
                          <div>
                            <p className="text-xs uppercase tracking-wide text-zinc-500">
                              Deadline
                            </p>

                            <p className="mt-1 font-medium text-zinc-300">
                              {new Date(
                                task.deadline
                              ).toLocaleDateString()}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    {actions.length > 0 && (
                      <div className="flex flex-wrap gap-2 border-t border-zinc-800 pt-4">
                        {actions.map((action) => (
                          <button
                            key={action.status}
                            disabled={isUpdating}
                            onClick={() =>
                              changeStatus(
                                task.id,
                                action.status
                              )
                            }
                            className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {isUpdating
                              ? "Updating..."
                              : action.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}