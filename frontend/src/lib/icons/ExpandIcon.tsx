import { IconBase, type IconProps } from "./Icon";

export function ExpandIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6" />
    </IconBase>
  );
}
