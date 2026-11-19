import localFont from "next/font/local";

// All three shortlisted packs are available; theme.css selects the active pair.
const jersey = localFont({ src: "./fonts/jersey15.ttf", variable: "--font-jersey15", preload: false });
const rubik = localFont({ src: [{ path: "./fonts/rubik.ttf", weight: "400" }, { path: "./fonts/rubik-bold.ttf", weight: "700" }], variable: "--font-rubik", preload: false });
const bricolage = localFont({ src: [{ path: "./fonts/bricolage.ttf", weight: "400" }, { path: "./fonts/bricolage-bold.ttf", weight: "700" }], variable: "--font-bricolage", preload: false });
const newsreader = localFont({ src: [{ path: "./fonts/newsreader.ttf", weight: "400" }, { path: "./fonts/newsreader-bold.ttf", weight: "700" }], variable: "--font-newsreader", preload: false });
const cormorant = localFont({ src: [{ path: "./fonts/cormorant.ttf", weight: "400" }, { path: "./fonts/cormorant-bold.ttf", weight: "700" }], variable: "--font-cormorant", preload: false });
const literata = localFont({ src: [{ path: "./fonts/literata.ttf", weight: "400" }, { path: "./fonts/literata-bold.ttf", weight: "700" }], variable: "--font-literata", preload: false });

export const fontVariables = [jersey, rubik, bricolage, newsreader, cormorant, literata]
  .map((font) => font.variable)
  .join(" ");
