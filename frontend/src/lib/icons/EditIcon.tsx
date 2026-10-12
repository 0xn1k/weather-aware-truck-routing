import { IconBase, type IconProps } from "./Icon";

export function EditIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 20h4L19 9l-4-4L4 16z M13 7l4 4" />
    </IconBase>
  );
}
