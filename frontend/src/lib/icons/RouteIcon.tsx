import { IconBase, type IconProps } from "./Icon";

export function RouteIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="6" cy="18" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <path d="M8 16.5C14 15 9 9 16 7.5" />
    </IconBase>
  );
}
