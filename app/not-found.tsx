import Link from "next/link";

export default function NotFound() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-24 text-center">
      <h1 className="text-4xl font-bold text-foreground mb-4">404</h1>
      <p className="text-tone-400 mb-8">Player not found.</p>
      <Link
        href="/"
        className="rounded-lg bg-scored-500 px-5 py-2 text-sm font-semibold text-background hover:bg-scored-300 transition"
      >
        Back to search
      </Link>
    </main>
  );
}
