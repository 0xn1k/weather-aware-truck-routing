import { IconBase, type IconProps } from "./Icon";

export function TruckIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M2 7h11v9H2z M13 10h4l3.5 3.5V16H13z" />
      <circle cx="6" cy="17.5" r="1.8" />
      <circle cx="16.5" cy="17.5" r="1.8" />
    </IconBase>
  );
}
