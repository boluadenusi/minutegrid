This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

The home page shows players at top-5 league clubs who have scored in all 90
minutes and those missing one to three minutes. `/coverage` lists the
competitions counted (`scripts/scope.py`): the Premier League, LaLiga, Serie A,
Bundesliga and Ligue 1; their domestic cups and super cups (FA Cup, EFL/Carabao
Cup, Community Shield, Copa del Rey, Supercopa, DFB-Pokal, DFL-Supercup, Coppa
Italia, Supercoppa, Coupe de France, Coupe de la Ligue until 2020, Trophée des
Champions); and the Champions League, Europa League, Conference League and UEFA
Super Cup (no qualifying rounds). Only goals from the last 10 years count.

## Data

- **History:** Transfermarkt up to its last day (2026-07-06), read from the
  snapshot in `data/base/`. For the cups and super cups, each season uses
  whichever of Transfermarkt and ESPN has more goals; the EFL Cup, Coupe de
  France and Coupe de la Ligue come from ESPN only (Transfermarkt lacks them).
  Sources are never mixed within one competition-season.
- **Live:** ESPN's public feed for everything after Transfermarkt's last day.
  PitchAPI is retired; its scripts are kept but not used.
- **Players:** only players in a current ESPN squad of a top-5 league club.
  They are matched to Transfermarkt by date of birth and name, then club and
  name, then by goals. Players Transfermarkt does not know get an ESPN-only page.
  Unmatched players are listed in `data/espn/review.csv` and not shown.

### Updates run by themselves

`.github/workflows/update-data.yml` runs every 3 hours on GitHub: it fetches the
last few days from ESPN and the squads (once a day), rebuilds `data/`, and
commits the changes. A host connected to the repository (e.g. Vercel)
redeploys on that commit. Use "Run workflow" in the Actions tab to run it now.

### One-time setup (on your computer, before the first push)

```
pip install -r scripts/requirements.txt
python scripts/make_tm_snapshot.py      # needs ../footy-pipeline; writes data/base/
python scripts/espn_sync.py --backfill  # 10 years of cups, recent league seasons, squads
python scripts/espn_sync.py --report    # coverage per competition and season
python scripts/prep.py
```

Commit `data/` (including `data/base/` and `data/espn/`). `data/espn_cache/` is
ignored. The backfill can be rerun safely; finished seasons are skipped.

Open player search from the search control or with Cmd+K (Ctrl+K on Windows
and Linux). Search on a player page morphs the current visualization to the
selected player.

Run the board generation tests with
`python -m unittest discover -s tests -p test_boards.py`.

Player pages show chains of consecutive scored
minutes from 1 to 90; minutes 45 and 90 include added time. Select a node to
move the shared timeline, or hover or focus it to inspect its chain. The
Player links, including older `?view=chain` links, open the chain view directly.
Player link previews use the chain share card.

The chain calculation can be checked with Node 22 or later:
`node --experimental-strip-types --test tests/chains.test.mjs`.
To check server-rendered player pages, run `npm run build`, start
`npm run start -- -p 3011`, then run
`node --test tests/player-chain-page.test.mjs`. Set `TEST_BASE_URL` to use
a different running server.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

## Theme

The theme is [Pixel Arcade](https://palletism.art/collections/pixel-arcade):
midnight, arcade red, coin blue and screen white, with Jersey 15 and Rubik.
The app uses no pack imagery. Colors, derived shades, Tailwind color mappings,
font selection and share-card font names are in `app/theme.css`. Font files
are self-hosted with `next/font/local` and are distributed with their Google
Fonts SIL Open Font Licenses in `app/fonts/`.

To switch to [Halftone Press](https://palletism.art/collections/halftone-press)
or [Graphite Sketch](https://palletism.art/collections/graphite-sketch),
uncomment its `:root` block at the end of `app/theme.css`, leave the other
block commented, and rebuild. Both alternative font pairs are already
available locally. The share cards read the same active tokens.

The shared heat buckets are 1, 2, 3–4 and 5+ goals. Their brightness increases
with the count; dashed borders and rings independently mark missing minutes.
Run `node --experimental-strip-types --test tests/theme.test.mjs` to check
contrast, simulated color-vision deficiencies, and image-renderer font support.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
