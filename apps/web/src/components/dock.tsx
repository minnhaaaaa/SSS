import { AnimatePresence, LazyMotion, domAnimation, m, useMotionValue, useSpring, useTransform, type MotionValue, type SpringOptions } from "motion/react";
import { useMemo, useRef, useState, type ReactNode } from "react";

import "./dock.css";

export interface DockItemData {
  readonly icon: ReactNode;
  readonly label: string;
  readonly onClick: () => void;
  readonly active?: boolean;
  readonly className?: string;
}

interface DockProps {
  readonly items: readonly DockItemData[];
  readonly className?: string;
  readonly distance?: number;
  readonly panelHeight?: number;
  readonly baseItemSize?: number;
  readonly dockHeight?: number;
  readonly magnification?: number;
  readonly spring?: SpringOptions;
}

interface DockItemProps extends DockItemData {
  readonly mouseX: MotionValue<number>;
  readonly spring: SpringOptions;
  readonly distance: number;
  readonly magnification: number;
  readonly baseItemSize: number;
}

function DockItem({
  label,
  icon,
  onClick,
  active = false,
  className = "",
  mouseX,
  spring,
  distance,
  magnification,
  baseItemSize,
}: DockItemProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const mouseDistance = useTransform(mouseX, (value) => {
    const rect = ref.current?.getBoundingClientRect() ?? { x: 0, width: baseItemSize };
    return value - rect.x - rect.width / 2;
  });
  const targetSize = useTransform(
    mouseDistance,
    [-distance, 0, distance],
    [baseItemSize, magnification, baseItemSize],
  );
  const size = useSpring(targetSize, spring);
  const lift = useTransform(size, [baseItemSize, magnification], [0, -4]);

  return (
    <m.button
      ref={ref}
      type="button"
      style={{ width: size, height: size, y: lift }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      onFocus={() => setIsHovered(true)}
      onBlur={() => setIsHovered(false)}
      onClick={onClick}
      className={`dock-item ${active ? "dock-item--active" : ""} ${className}`.trim()}
      aria-current={active ? "page" : undefined}
      aria-label={label}
    >
      <span className="dock-icon" aria-hidden="true">{icon}</span>
      <AnimatePresence>
        {isHovered && (
          <m.span
            initial={{ opacity: 0, y: 2 }}
            animate={{ opacity: 1, y: -7 }}
            exit={{ opacity: 0, y: 2 }}
            transition={{ duration: 0.14 }}
            className="dock-label"
            role="tooltip"
          >
            {label}
          </m.span>
        )}
      </AnimatePresence>
    </m.button>
  );
}

export default function Dock({
  items,
  className = "",
  spring = { mass: 0.1, stiffness: 150, damping: 12 },
  magnification = 45,
  distance = 150,
  panelHeight = 48,
  dockHeight = 68,
  baseItemSize = 35,
}: DockProps) {
  const mouseX = useMotionValue(Number.POSITIVE_INFINITY);
  const hovered = useMotionValue(0);
  const maxHeight = useMemo(
    () => Math.max(dockHeight, magnification + magnification / 2 + 4),
    [dockHeight, magnification],
  );
  const heightTarget = useTransform(hovered, [0, 1], [panelHeight, maxHeight]);
  const height = useSpring(heightTarget, spring);

  return (
    <LazyMotion features={domAnimation} strict>
      <m.div style={{ height }} className="dock-outer">
        <m.div
          onMouseMove={({ pageX }) => {
            hovered.set(1);
            mouseX.set(pageX);
          }}
          onMouseLeave={() => {
            hovered.set(0);
            mouseX.set(Number.POSITIVE_INFINITY);
          }}
          className={`dock-panel ${className}`.trim()}
          style={{ height: panelHeight }}
          role="toolbar"
          aria-label="Primary navigation"
        >
          {items.map((item) => (
            <DockItem
              key={item.label}
              {...item}
              mouseX={mouseX}
              spring={spring}
              distance={distance}
              magnification={magnification}
              baseItemSize={baseItemSize}
            />
          ))}
        </m.div>
      </m.div>
    </LazyMotion>
  );
}
