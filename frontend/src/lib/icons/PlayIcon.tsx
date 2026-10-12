import { IconBase, type IconProps } from "./Icon";

export function PlayIcon(props: IconProps) {
  return (
    <IconBase {...props} fill="currentColor">
      {/* Centred in the 24x24 viewBox (bounding box 9-17 x, 8-16 y — a
          touch right of dead-centre, the usual convention so the pointed
          tip doesn't read as left-heavy) — the button that wraps this
          flex-centres the <svg> itself, but that can't fix a triangle
          drawn off-centre within its own canvas, which is what the old
          path (bounding box 4-13.5, 2.5-13.5) did. */}
      <path d="M9 8l8 4-8 4z" />
    </IconBase>
  );
}
