import { useState } from "react";
import logoAsset from "../assets/logo.png";

interface AgroLogoProps {
  className?: string;
  textClassName?: string;
}

export function AgroLogo({
  className = "w-9 h-9 rounded-full object-cover",
  textClassName = "font-display font-bold text-forest text-xs",
}: AgroLogoProps) {
  const [src, setSrc] = useState<string>(logoAsset || "/logo.png");
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span
        className={`inline-flex items-center justify-center rounded-full bg-forest/10 px-2 py-1 ${textClassName}`}
        aria-label="Agro AI"
      >
        Agro AI
      </span>
    );
  }

  return (
    <img
      src={src}
      alt="Agro AI"
      className={className}
      onError={() => {
        if (src !== "/logo.png") {
          setSrc("/logo.png");
        } else {
          setFailed(true);
        }
      }}
    />
  );
}
