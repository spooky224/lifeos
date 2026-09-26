"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { name: "Dashboard", href: "/" },
  { name: "Goals", href: "/goals" },
  { name: "Tasks", href: "/tasks" },
  { name: "Routines", href: "/routines" },
  { name: "Calendar", href: "/calendar" },
  { name: "AI Chat", href: "/chat" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 flex h-screen w-64 flex-col border-r border-zinc-800 bg-zinc-950 p-6 text-white">
      <div className="mb-10">
        <h1 className="text-2xl font-bold tracking-tight">LIFEOS</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Personal Operating System
        </p>
      </div>

      <nav className="flex flex-1 flex-col gap-2">
        {navigation.map((item) => {
          const active = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-xl px-4 py-3 text-sm transition ${
                active
                  ? "bg-white text-black"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
              }`}
            >
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-zinc-800 pt-5">
        <p className="text-xs text-zinc-600">LIFEOS v0.1.0</p>
        <p className="mt-1 text-xs text-zinc-600">Agentic Personal OS</p>
      </div>
    </aside>
  );
}
