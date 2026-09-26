export default function WorkspaceCalendar() {
    return (
      <div className="space-y-6">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <h3 className="text-lg font-semibold">
            Upcoming Events
          </h3>
  
          <p className="mt-2 text-sm text-zinc-500">
            Google Calendar events will appear here.
          </p>
        </div>
  
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <h3 className="text-lg font-semibold">
            Available Time
          </h3>
  
          <p className="mt-2 text-sm text-zinc-500">
            Free work slots will appear here.
          </p>
        </div>
      </div>
    );
  }