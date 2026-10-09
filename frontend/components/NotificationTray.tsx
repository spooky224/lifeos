"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api";

const POLL_INTERVAL_MS = 15_000;
const SNOOZE_MS = 15 * 60 * 1000;
const SNOOZE_STORAGE_KEY = "lifeos.snoozedNotifications";

export type LifeosNotification = {
  id: string;
  type: "due_now" | "overdue_unstarted" | "overdue_in_progress";
  task_id: number;
  calendar_event_id: number;
  title: string;
  message: string;
  start_time: string;
  end_time: string;
  actions: string[];
};

const ACTION_LABELS: Record<string, string> = {
  start: "Start now",
  completed: "Done",
  missed: "Missed",
  cancelled: "Cancel",
  reschedule: "Reschedule",
};

function loadSnoozed(): Record<string, number> {
  try {
    const raw = localStorage.getItem(SNOOZE_STORAGE_KEY);
    const parsed: Record<string, number> = raw ? JSON.parse(raw) : {};
    const now = Date.now();

    return Object.fromEntries(
      Object.entries(parsed).filter(([, until]) => until > now)
    );
  } catch {
    return {};
  }
}

function saveSnoozed(snoozed: Record<string, number>) {
  try {
    localStorage.setItem(SNOOZE_STORAGE_KEY, JSON.stringify(snoozed));
  } catch {
    // Storage unavailable: snoozing just won't persist across reloads.
  }
}

type Props = {
  /** Reschedule needs a conversation, so it is handed to the chat. */
  onReschedule: (notification: LifeosNotification) => void;
  /** True while the chat is waiting on an answer; don't start another flow. */
  rescheduleDisabled?: boolean;
};

export default function NotificationTray({
  onReschedule,
  rescheduleDisabled = false,
}: Props) {
  const [notifications, setNotifications] = useState<LifeosNotification[]>([]);
  const [snoozed, setSnoozed] = useState<Record<string, number>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setSnoozed(loadSnoozed());
  }, []);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/notifications`);

      if (!response.ok) {
        return;
      }

      const data = await response.json();
      setNotifications(data.notifications ?? []);
    } catch {
      // Backend unreachable: keep showing what we have, retry next tick.
    }
  }, []);

  useEffect(() => {
    refresh();

    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };

    document.addEventListener("visibilitychange", onVisible);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  function snooze(id: string) {
    const next = { ...loadSnoozed(), [id]: Date.now() + SNOOZE_MS };
    saveSnoozed(next);
    setSnoozed(next);
  }

  async function runAction(notification: LifeosNotification, action: string) {
    if (action === "reschedule") {
      snooze(notification.id);
      onReschedule(notification);
      return;
    }

    setBusyId(notification.id);
    setErrors((current) => {
      const { [notification.id]: _removed, ...rest } = current;
      return rest;
    });

    try {
      const response = await fetch(`${API_URL}/notifications/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: notification.task_id, action }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "That action failed.");
      }

      // Optimistic removal, then confirm against the source of truth.
      setNotifications((current) =>
        current.filter((item) => item.id !== notification.id)
      );
      await refresh();
    } catch (error) {
      setErrors((current) => ({
        ...current,
        [notification.id]:
          error instanceof Error ? error.message : "That action failed.",
      }));
    } finally {
      setBusyId(null);
    }
  }

  const now = Date.now();
  const visible = notifications.filter(
    (item) => (snoozed[item.id] ?? 0) <= now
  );

  if (visible.length === 0) {
    return null;
  }

  return (
    <section
      aria-live="polite"
      className="space-y-3 rounded-2xl border border-amber-900/60 bg-amber-950/20 p-4"
    >
      <div className="flex items-center gap-2 text-sm font-medium text-amber-200">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
        </span>
        Needs your attention ({visible.length})
      </div>

      {visible.map((item) => (
        <div
          key={item.id}
          className="rounded-xl border border-zinc-800 bg-zinc-900 p-4"
        >
          <p className="text-sm text-zinc-200">{item.message}</p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {item.actions.map((action) => {
              const isReschedule = action === "reschedule";

              return (
                <button
                  key={action}
                  onClick={() => runAction(item, action)}
                  disabled={
                    busyId === item.id ||
                    (isReschedule && rescheduleDisabled)
                  }
                  title={
                    isReschedule && rescheduleDisabled
                      ? "Finish the current question in the chat first."
                      : undefined
                  }
                  className={
                    action === "start" || action === "completed"
                      ? "rounded-lg bg-white px-3 py-1.5 text-xs font-medium text-black hover:bg-zinc-200 disabled:opacity-40"
                      : "rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 disabled:opacity-40"
                  }
                >
                  {ACTION_LABELS[action] ?? action}
                </button>
              );
            })}

            <button
              onClick={() => snooze(item.id)}
              disabled={busyId === item.id}
              className="ml-auto text-xs text-zinc-500 hover:text-zinc-300"
            >
              Remind me later
            </button>
          </div>

          {errors[item.id] && (
            <p className="mt-2 text-xs text-red-400">{errors[item.id]}</p>
          )}
        </div>
      ))}
    </section>
  );
}