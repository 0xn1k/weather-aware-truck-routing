import { IconBase, type IconProps } from "./Icon";

export function WarningIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 3l9.5 17h-19z" />
      <path d="M12 10v4.5M12 17.3v.2" />
    </IconBase>
  );
}
