const API_URL = "http://127.0.0.1:8000/api";

export interface Goal {
  id: number;
  name: string;
  priority: string;
  status: string;
  created_at: string;
}

export interface Task {
  id: number;
  goal_id: number;
  title: string;
  description: string | null;
  estimated_duration_minutes: number;
  priority: string;
  status: string;
  deadline: string | null;
}

export interface CalendarEvent {
  id: number;
  task_id: number;
  google_event_id: string;
  title: string;
  start_time: string;
  end_time: string;
  status: string;
}

export async function getGoals(): Promise<Goal[]> {
  const response = await fetch(`${API_URL}/goals`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch goals");
  }

  return response.json();
}

export async function getTasks(): Promise<Task[]> {
  const response = await fetch(`${API_URL}/tasks`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch tasks");
  }

  return response.json();
}

export async function getCalendarEvents(): Promise<CalendarEvent[]> {
  const response = await fetch(`${API_URL}/calendar`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch calendar events");
  }

  return response.json();
}


export type TaskStatus =
  | "planned"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "postponed"
  | "missed"
  | "cancelled";

export async function updateTaskStatus(
  taskId: number,
  status: TaskStatus
): Promise<Task> {
  const response = await fetch(`${API_URL}/tasks/${taskId}/status`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      status,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail || "Failed to update task status"
    );
  }

  return response.json();
}

export interface Routine {
  id: number;
  goal_id: number | null;
  name: string;
  description: string | null;
  frequency: string;
  days_of_week: number[] | null;
  preferred_time: string | null;
  duration_minutes: number;
  priority: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export async function getRoutines(): Promise<Routine[]> {
  const response = await fetch(`${API_URL}/routines`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch routines");
  }

  return response.json();
}

export async function createRoutine(
  routine: Omit<
    Routine,
    "id" | "created_at" | "updated_at" | "is_active"
  >
): Promise<Routine> {
  const response = await fetch(`${API_URL}/routines`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ...routine,
      is_active: true,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail || "Failed to create routine"
    );
  }

  return response.json();
}

export async function activateRoutine(
  routineId: number
): Promise<{ id: number; is_active: boolean }> {
  const response = await fetch(
    `${API_URL}/routines/${routineId}/activate`,
    {
      method: "PATCH",
    }
  );

  if (!response.ok) {
    throw new Error("Failed to activate routine");
  }

  return response.json();
}

export async function deactivateRoutine(
  routineId: number
): Promise<{ id: number; is_active: boolean }> {
  const response = await fetch(
    `${API_URL}/routines/${routineId}/deactivate`,
    {
      method: "PATCH",
    }
  );

  if (!response.ok) {
    throw new Error("Failed to deactivate routine");
  }

  return response.json();
}

export async function deleteRoutine(
  routineId: number
): Promise<void> {
  const response = await fetch(
    `${API_URL}/routines/${routineId}`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    throw new Error("Failed to delete routine");
  }
}