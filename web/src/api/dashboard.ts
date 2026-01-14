export async function fetchDashboard(token: string) {
  const r = await fetch("/dashboard/", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`Dashboard ${r.status}`);
  return r.json();
}
