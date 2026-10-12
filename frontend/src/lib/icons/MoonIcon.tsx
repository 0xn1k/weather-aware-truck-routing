import { IconBase, type IconProps } from "./Icon";

export function MoonIcon(props: IconProps) {
  return (
    <IconBase {...props} strokeLinejoin="round">
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z" />
    </IconBase>
  );
}
