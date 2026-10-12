import { IconBase, type IconProps } from "./Icon";

export function PauseIcon(props: IconProps) {
  return (
    <IconBase {...props} fill="currentColor" stroke="none">
      <rect x="5" y="4" width="4" height="16" rx="1" />
      <rect x="15" y="4" width="4" height="16" rx="1" />
    </IconBase>
  );
}
