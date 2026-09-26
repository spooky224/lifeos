"use client";

import { useEffect, useState } from "react";
import { getCalendarEvents, CalendarEvent } from "@/lib/api";
import Sidebar from "@/components/Sidebar";

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCalendarEvents()
      .then(setEvents)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <Sidebar />

      <main className="ml-64 p-8">
        <div className="mb-8">
          <p className="text-sm font-medium text-blue-400">LIFEOS</p>
          <h1 className="mt-1 text-3xl font-bold">Calendar</h1>
          <p className="mt-2 text-zinc-400">
            Actions scheduled by LIFEOS and synchronized with your calendar.
          </p>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-zinc-400">
            Loading calendar...
          </div>
        ) : events.length === 0 ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
            <p className="text-lg font-medium">No scheduled events</p>
            <p className="mt-2 text-sm text-zinc-500">
              Approved LIFEOS calendar actions will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {events.map((event) => (
              <div
                key={event.id}
                className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 transition hover:border-zinc-700"
              >
                <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <div className="h-3 w-3 rounded-full bg-blue-400" />

                      <h2 className="text-lg font-semibold">
                        {event.title}
                      </h2>

                      <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
                        {event.status}
                      </span>
                    </div>

                    <p className="mt-3 text-sm text-zinc-400">
                      Google Calendar event
                    </p>
                  </div>

                  <div className="text-left md:text-right">
                    <p className="text-sm font-medium text-zinc-200">
                      {new Date(event.start_time).toLocaleDateString()}
                    </p>

                    <p className="mt-1 text-sm text-zinc-400">
                      {new Date(event.start_time).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}{" "}
                      –{" "}
                      {new Date(event.end_time).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}