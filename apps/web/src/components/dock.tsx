import { AnimatePresence, LazyMotion, domAnimation, m, useMotionValue, useReducedMotion, useSpring, useTransform, type MotionValue, type SpringOptions } from "motion/react";
import { useMemo, useRef, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";

import "./dock.css";

export interface DockItemData {
  readonly icon: ReactNode;
  readonly label: string;
  readonly to: string;
  readonly end?: boolean;
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
  readonly reducedMotion: boolean;
}

function DockItem({
  label,
  icon,
  to,
  end = false,
  className = "",
  mouseX,
  spring,
  distance,
  magnification,
  baseItemSize,
  reducedMotion,
}: DockItemProps) {
  const ref = useRef<HTMLDivElement>(null);
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
    <m.div
      ref={ref}
      style={reducedMotion
        ? { width: baseItemSize, height: baseItemSize }
        : { width: size, height: size, y: lift }}
      onHoverStart={() => {
        if (!reducedMotion) setIsHovered(true);
      }}
      onHoverEnd={() => {
        if (!reducedMotion) setIsHovered(false);
      }}
      onFocus={() => {
        if (!reducedMotion) setIsHovered(true);
      }}
      onBlur={() => {
        if (!reducedMotion) setIsHovered(false);
      }}
      className="dock-item-motion"
    >
      <NavLink
        to={to}
        end={end}
        className={({ isActive }) =>
          `dock-item ${isActive ? "dock-item--active" : ""} ${className}`.trim()
        }
        aria-label={label}
      >
        <span className="dock-icon" aria-hidden="true">{icon}</span>
        {reducedMotion ? (
          <span className="dock-label dock-label--static" role="tooltip" aria-hidden="true">
            <span className="dock-label__content">{label}</span>
          </span>
        ) : (
          <span className="dock-label" role="tooltip" aria-hidden="true">
            <AnimatePresence>
              {isHovered && (
                <m.span
                  initial={{ opacity: 0, y: 2 }}
                  animate={{ opacity: 1, y: -7 }}
                  exit={{ opacity: 0, y: 2 }}
                  transition={{ duration: 0.14 }}
                  className="dock-label__content"
                >
                  {label}
                </m.span>
              )}
            </AnimatePresence>
          </span>
        )}
      </NavLink>
    </m.div>
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
  const reducedMotion = useReducedMotion() ?? false;
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
      <m.div
        style={reducedMotion ? { height: panelHeight } : { height }}
        className="dock-outer"
        data-reduced-motion={reducedMotion}
      >
        <nav
          onMouseMove={({ clientX }) => {
            if (reducedMotion) return;
            hovered.set(1);
            mouseX.set(clientX);
          }}
          onMouseLeave={() => {
            if (reducedMotion) return;
            hovered.set(0);
            mouseX.set(Number.POSITIVE_INFINITY);
          }}
          className={`dock-panel ${className}`.trim()}
          style={{ height: panelHeight }}
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
              reducedMotion={reducedMotion}
            />
          ))}
        </nav>
      </m.div>
    </LazyMotion>
  );
}
