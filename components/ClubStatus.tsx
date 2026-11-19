import type { Club } from "@/lib/data";
import Avatar from "@/components/Avatar";

interface ClubStatusProps {
  club?: Club | null;
  active?: boolean;
  asOf?: string;
}

export default function ClubStatus({ club, active, asOf }: ClubStatusProps) {
  if (!asOf) return null;
  return (
    <>
      {club?.name && (
        <span className="flex items-center gap-1.5 text-sm text-tone-400" title={`Club as of ${asOf}`}>
          <Avatar src={club.logo} name={club.name} size={18} kind="logo" />
          {club.name}
          <span className="sr-only">, club as of {asOf}</span>
        </span>
      )}
      {active === false && (
        <span className="block text-xs text-tone-400">Not in a top flight (as of {asOf})</span>
      )}
    </>
  );
}
