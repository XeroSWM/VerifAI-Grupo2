export async function fetchGeminiAuditReport({ backendIp, apiKey, profile, psychometrics, frequency }) {
  const headers = { "Content-Type": "application/json" };
  if (apiKey && apiKey.trim()) {
    headers["X-Gemini-Api-Key"] = apiKey.trim();
  }

  const response = await fetch("http://" + backendIp + ":8000/api/ai/gemini-report", {
    method: "POST",
    headers,
    body: JSON.stringify({
      profile: profile || {},
      psychometrics: psychometrics || {},
      frequency: frequency || "Moderada",
    }),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Error HTTP " + response.status + " al consultar Gemini");
  }
  return await response.json();
}