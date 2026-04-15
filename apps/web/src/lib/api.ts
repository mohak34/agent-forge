const API_BASE = "http://localhost:8000/api/v0";

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
