import { IconBase, type IconProps } from "./Icon";

export function CloseIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M5 5l14 14M19 5L5 19" />
    </IconBase>
  );
}
