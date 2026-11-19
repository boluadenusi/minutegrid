/** Display helpers for goal details, shared by the player header and the goal panel. */

export function formatGoalDate(dStr: string): string {
  if (!dStr) return "";
  const parts = dStr.split("-");
  if (parts.length < 3) return dStr;
  const year = parts[0];
  const month = parseInt(parts[1], 10);
  const day = parseInt(parts[2], 10);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${day} ${months[month - 1] || parts[1]} ${year}`;
}

export function formatCompetition(comp: string): string {
  if (!comp) return "Unknown competition";
  const special: Record<string, string> = {
    "uefa-champions-league": "UEFA Champions League",
    "uefa-europa-league": "UEFA Europa League",
    "europa-league": "Europa League",
    "premier-league": "Premier League",
    "fa-cup": "FA Cup",
    "efl-cup": "EFL Cup",
    bundesliga: "Bundesliga",
    "dfb-pokal": "DFB-Pokal",
    laliga: "LaLiga",
    "copa-del-rey": "Copa del Rey",
    "serie-a": "Serie A",
    "coppa-italia": "Coppa Italia",
    "ligue-1": "Ligue 1",
    "world-cup": "World Cup",
    "uefa-euro": "UEFA Euro",
  };
  const key = comp.toLowerCase();
  if (special[key]) return special[key];

  return comp
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
