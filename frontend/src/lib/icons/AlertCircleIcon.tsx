import { IconBase, type IconProps } from "./Icon";

export function AlertCircleIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v6M12 16.5v.2" />
    </IconBase>
  );
}
