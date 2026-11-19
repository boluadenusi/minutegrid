"use client";

import { useState } from "react";

interface AvatarProps {
  src?: string | null;
  /** Used for the initials fallback; the image itself is decorative (the name is shown next to it). */
  name: string;
  size?: number;
  /** "photo" is a round player photo with an initials fallback; "logo" is a club badge that
   * renders nothing when missing. */
  kind?: "photo" | "logo";
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
}

export default function Avatar({ src, name, size = 40, kind = "photo" }: AvatarProps) {
  const [failed, setFailed] = useState(false);
  const style = { inlineSize: size, blockSize: size };
  if (!src || failed) {
    if (kind === "logo") return null;
    return (
      <span className="avatar avatar-photo avatar-fallback" style={{ ...style, fontSize: Math.max(10, size * 0.32) }}
        aria-hidden="true">
        {initials(name)}
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- remote CDN or /public files, no optimisation needed
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className={`avatar avatar-${kind}`}
      style={style}
      onError={() => setFailed(true)}
    />
  );
}
