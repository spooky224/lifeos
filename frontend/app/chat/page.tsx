"use client";

import { useState } from "react";
import Link from "next/link";

const API_URL = "http://127.0.0.1:8000/api";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [threadId] = useState(
    () => `lifeos-${Date.now()}`
  );
  const [pendingApproval, setPendingApproval] = useState(false);
  const [loading, setLoading] = useState(false);

  async function sendMessage() {
    if (!message.trim() || loading) {
      return;
    }

    const userMessage = message.trim();

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: userMessage,
      },
    ]);

    setMessage("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage,
          thread_id: threadId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Something went wrong.");
      }

      if (data.status === "approval_required") {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: data.message,
          },
        ]);

        setPendingApproval(true);
      } else {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: "Done. LIFEOS completed the requested action.",
          },
        ]);
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            error instanceof Error
              ? error.message
              : "Unable to reach LIFEOS.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleApproval(decision: "approved" | "rejected") {
    setLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/approvals/${threadId}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            decision,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Approval failed.");
      }

      setPendingApproval(false);

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            decision === "approved"
              ? "Approved. The action has been executed and persisted."
              : "Understood. I cancelled the proposed action.",
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            error instanceof Error
              ? error.message
              : "Unable to process the decision.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <aside className="fixed left-0 top-0 flex h-screen w-64 flex-col border-r border-zinc-800 bg-zinc-950 p-6">
        <div className="mb-10">
          <Link href="/">
            <h1 className="text-2xl font-bold tracking-tight">
              LIFEOS
            </h1>
          </Link>

          <p className="mt-1 text-sm text-zinc-500">
            Personal Operating System
          </p>
        </div>

        <nav className="flex flex-1 flex-col gap-2">
          <NavLink href="/" label="Dashboard" />
          <NavLink href="/goals" label="Goals" />
          <NavLink href="/tasks" label="Tasks" />
          <NavLink href="/calendar" label="Calendar" />
          <NavLink href="/chat" label="AI Chat" active />
        </nav>

        <p className="text-xs text-zinc-600">
          LIFEOS v0.1.0
        </p>
      </aside>

      <main className="ml-64 flex min-h-screen flex-col">
        <header className="border-b border-zinc-800 px-10 py-6">
          <p className="text-sm text-zinc-500">
            LIFEOS AI
          </p>

          <h2 className="mt-1 text-2xl font-semibold">
            Personal Command Center
          </h2>
        </header>

        <div className="flex flex-1 flex-col">
          <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-8 py-10">
            {messages.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center text-center">
                <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900 text-xl">
                  AI
                </div>

                <h3 className="text-3xl font-semibold">
                  What should we plan?
                </h3>

                <p className="mt-3 max-w-lg text-zinc-500">
                  Tell LIFEOS what you want to accomplish. It can reason
                  about your goals, tasks, schedule, and available time.
                </p>

                <div className="mt-8 grid gap-3 text-left sm:grid-cols-2">
                  <Suggestion
                    text="Schedule three hours for my AI project this week."
                    onClick={setMessage}
                  />

                  <Suggestion
                    text="Help me plan my priorities for this week."
                    onClick={setMessage}
                  />
                </div>
              </div>
            ) : (
              <div className="flex-1 space-y-6">
                {messages.map((item, index) => (
                  <div
                    key={index}
                    className={
                      item.role === "user"
                        ? "flex justify-end"
                        : "flex justify-start"
                    }
                  >
                    <div
                      className={
                        item.role === "user"
                          ? "max-w-2xl rounded-2xl bg-white px-5 py-4 text-sm text-black"
                          : "max-w-2xl rounded-2xl border border-zinc-800 bg-zinc-900 px-5 py-4 text-sm text-zinc-200"
                      }
                    >
                      {item.content}
                    </div>
                  </div>
                ))}

                {pendingApproval && (
                  <div className="rounded-2xl border border-zinc-700 bg-zinc-900 p-6">
                    <p className="text-sm font-medium">
                      Human approval required
                    </p>

                    <p className="mt-2 text-sm text-zinc-500">
                      LIFEOS has proposed an action. Review it above before
                      allowing it to modify your calendar.
                    </p>

                    <div className="mt-5 flex gap-3">
                      <button
                        onClick={() =>
                          handleApproval("approved")
                        }
                        disabled={loading}
                        className="rounded-xl bg-white px-5 py-3 text-sm font-medium text-black hover:bg-zinc-200 disabled:opacity-50"
                      >
                        Approve
                      </button>

                      <button
                        onClick={() =>
                          handleApproval("rejected")
                        }
                        disabled={loading}
                        className="rounded-xl border border-zinc-700 px-5 py-3 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="mt-8">
              <div className="flex items-end gap-3 rounded-2xl border border-zinc-700 bg-zinc-900 p-3">
                <textarea
                  value={message}
                  onChange={(event) =>
                    setMessage(event.target.value)
                  }
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey
                    ) {
                      event.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder="Tell LIFEOS what you want to accomplish..."
                  rows={2}
                  className="flex-1 resize-none bg-transparent px-3 py-2 text-sm text-white outline-none placeholder:text-zinc-600"
                />

                <button
                  onClick={sendMessage}
                  disabled={loading || !message.trim()}
                  className="rounded-xl bg-white px-5 py-3 text-sm font-medium text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {loading ? "Thinking..." : "Send"}
                </button>
              </div>

              <p className="mt-3 text-center text-xs text-zinc-700">
                LIFEOS can propose actions. You remain in control of
                execution.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function NavLink({
  href,
  label,
  active = false,
}: {
  href: string;
  label: string;
  active?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`rounded-xl px-4 py-3 text-sm transition ${
        active
          ? "bg-white text-black"
          : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
      }`}
    >
      {label}
    </Link>
  );
}

function Suggestion({
  text,
  onClick,
}: {
  text: string;
  onClick: (value: string) => void;
}) {
  return (
    <button
      onClick={() => onClick(text)}
      className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-left text-sm text-zinc-400 transition hover:border-zinc-600 hover:text-white"
    >
      {text}
    </button>
  );
}
