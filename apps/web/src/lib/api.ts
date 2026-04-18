const API_BASE_ROOT = (import.meta.env.PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const API_BASE = `${API_BASE_ROOT}/api/v0`;

export type ChatThread = {
  id: string;
  title: string;
  memory_enabled: boolean;
  template_id: string | null;
  last_run_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  thread_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  turn_index: number;
  run_id: string | null;
  created_at: string;
};

export async function createRun(goal: string, memoryEnabled = false) {
  const response = await fetch(`${API_BASE}/goals`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ goal, memory_enabled: memoryEnabled })
  });

  if (!response.ok) {
    throw new Error("Failed to create run");
  }

  return response.json();
}

export async function getRunTimeline(runId: string) {
  const response = await fetch(`${API_BASE}/runs/${runId}/timeline`);
  if (!response.ok) {
    throw new Error("Failed to fetch run timeline");
  }
  return response.json();
}

export async function getRun(runId: string) {
  const response = await fetch(`${API_BASE}/runs/${runId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch run");
  }
  return response.json();
}

export async function listRuns(limit = 50) {
  const response = await fetch(`${API_BASE}/runs?limit=${limit}`);
  if (!response.ok) {
    throw new Error("Failed to fetch runs");
  }
  return response.json();
}

export async function createThread(title = "New chat", memoryEnabled = false, templateId: string | null = null) {
  const response = await fetch(`${API_BASE}/chat/threads`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      title,
      memory_enabled: memoryEnabled,
      template_id: templateId
    })
  });
  if (!response.ok) {
    throw new Error("Failed to create thread");
  }
  return response.json() as Promise<ChatThread>;
}

export async function listThreads(limit = 75) {
  const response = await fetch(`${API_BASE}/chat/threads?limit=${limit}`);
  if (!response.ok) {
    throw new Error("Failed to fetch threads");
  }
  return response.json() as Promise<ChatThread[]>;
}

export async function getThread(threadId: string) {
  const response = await fetch(`${API_BASE}/chat/threads/${threadId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch thread");
  }
  return response.json() as Promise<{ thread: ChatThread; messages: ChatMessage[] }>;
}

export async function listThreadMessages(threadId: string) {
  const response = await fetch(`${API_BASE}/chat/threads/${threadId}/messages`);
  if (!response.ok) {
    throw new Error("Failed to fetch thread messages");
  }
  return response.json() as Promise<ChatMessage[]>;
}

export async function sendThreadMessage(
  threadId: string,
  content: string,
  routeMode: "auto" | "direct" = "auto"
) {
  const response = await fetch(`${API_BASE}/chat/threads/${threadId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ content, route_mode: routeMode })
  });
  if (!response.ok) {
    throw new Error("Failed to send message");
  }
  return response.json();
}

export async function getRunTasks(runId: string) {
  const response = await fetch(`${API_BASE}/runs/${runId}/tasks`);
  if (!response.ok) {
    throw new Error("Failed to fetch run tasks");
  }
  return response.json();
}

export async function getTools() {
  const response = await fetch(`${API_BASE}/tools`);
  if (!response.ok) {
    throw new Error("Failed to fetch tools");
  }
  return response.json();
}

export async function listApprovals() {
  const response = await fetch(`${API_BASE}/approvals`);
  if (!response.ok) {
    throw new Error("Failed to fetch approvals");
  }
  return response.json();
}

export async function decideApproval(approvalId: string, decision: "approve" | "reject", reason = "") {
  const response = await fetch(`${API_BASE}/approvals/${approvalId}/decision`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ decision, reason })
  });

  if (!response.ok) {
    throw new Error("Failed to decide approval");
  }
  return response.json();
}

export async function listMemory() {
  const response = await fetch(`${API_BASE}/memory`);
  if (!response.ok) {
    throw new Error("Failed to fetch memory");
  }
  return response.json();
}

export async function listTemplates() {
  const response = await fetch(`${API_BASE}/agents`);
  if (!response.ok) {
    throw new Error("Failed to fetch templates");
  }
  return response.json();
}

export async function createTemplate(
  name: string,
  description: string,
  version: string,
  configJson: string
) {
  const response = await fetch(`${API_BASE}/agents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      name,
      description,
      version,
      config_json: configJson
    })
  });
  if (!response.ok) {
    throw new Error("Failed to create template");
  }
  return response.json();
}

export async function runFromTemplate(
  templateId: string,
  goal: string,
  memoryEnabled = false
) {
  const response = await fetch(`${API_BASE}/agents/${templateId}/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ goal, memory_enabled: memoryEnabled })
  });
  if (!response.ok) {
    throw new Error("Failed to run from template");
  }
  return response.json();
}

export async function exportTemplate(templateId: string) {
  const response = await fetch(`${API_BASE}/agents/${templateId}/export`);
  if (!response.ok) {
    throw new Error("Failed to export template");
  }
  return response.json();
}

export async function importTemplate(
  name: string,
  description: string,
  version: string,
  configJson: string
) {
  const response = await fetch(`${API_BASE}/agents/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      name,
      description,
      version,
      config_json: configJson
    })
  });
  if (!response.ok) {
    throw new Error("Failed to import template");
  }
  return response.json();
}
