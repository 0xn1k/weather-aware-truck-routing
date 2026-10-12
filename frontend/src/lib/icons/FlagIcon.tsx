import { IconBase, type IconProps } from "./Icon";

export function FlagIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M5 21V4M5 4h11l-2 4 2 4H5" />
    </IconBase>
  );
}
