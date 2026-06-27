"use client";

import { useEffect, useState } from "react";

const PRIMARY = "#0f2b5a";

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    background: "#ffffff",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
    padding: "3.5rem 2rem",
    position: "relative",
    overflow: "hidden",
    fontFamily: "sans-serif",
  },
  gridLineH: {
    position: "absolute",
    width: "100%",
    height: "1px",
    background: `rgba(15,43,90,0.05)`,
    left: 0,
  },
  gridLineV: {
    position: "absolute",
    height: "100%",
    width: "1px",
    background: `rgba(15,43,90,0.05)`,
    top: 0,
  },
  ring: {
    position: "absolute",
    borderRadius: "50%",
    border: `1px solid rgba(15,43,90,0.05)`,
    top: "50%",
    left: "50%",
    pointerEvents: "none",
  },
  cornerBase: {
    position: "absolute",
    width: 18,
    height: 18,
  },
  label: {
    fontFamily: "'DM Mono', 'Courier New', monospace",
    fontSize: 10,
    fontWeight: 300,
    letterSpacing: "0.22em",
    color: `rgba(15,43,90,0.4)`,
    textTransform: "uppercase" as const,
    marginBottom: "2.8rem",
  },
  titleWrap: {
    textAlign: "center" as const,
    marginBottom: "2.8rem",
    lineHeight: 0.88,
  },
  titleOutline: {
    fontFamily: "'Cormorant Garamond', Georgia, serif",
    fontSize: "clamp(64px, 12vw, 108px)",
    fontWeight: 300,
    letterSpacing: "-0.01em",
    color: "transparent",
    WebkitTextStroke: `1px rgba(15,43,90,0.15)`,
    display: "block",
    lineHeight: 0.88,
    userSelect: "none" as const,
  },
  titleSolid: {
    fontFamily: "'Cormorant Garamond', Georgia, serif",
    fontSize: "clamp(64px, 12vw, 108px)",
    fontWeight: 300,
    letterSpacing: "-0.01em",
    color: PRIMARY,
    display: "block",
    lineHeight: 0.88,
  },
  titleItalic: {
    fontFamily: "'Cormorant Garamond', Georgia, serif",
    fontSize: "clamp(64px, 12vw, 108px)",
    fontWeight: 300,
    fontStyle: "italic",
    letterSpacing: "-0.01em",
    color: `rgba(15,43,90,0.45)`,
    display: "block",
    lineHeight: 0.88,
  },
  dividerWrap: {
    width: "100%",
    maxWidth: 320,
    overflow: "hidden",
    marginBottom: "2.4rem",
  },
  sub: {
    fontFamily: "'Cormorant Garamond', Georgia, serif",
    fontSize: 15,
    fontWeight: 300,
    fontStyle: "italic",
    color: `rgba(15,43,90,0.45)`,
    letterSpacing: "0.04em",
    marginBottom: "3.2rem",
    textAlign: "center" as const,
    lineHeight: 1.6,
  },
  dotsWrap: {
    display: "flex",
    gap: 10,
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: "50%",
    background: PRIMARY,
  },
  badge: {
    position: "absolute",
    bottom: 32,
    right: 32,
    fontFamily: "'DM Mono', 'Courier New', monospace",
    fontSize: 9,
    fontWeight: 300,
    letterSpacing: "0.18em",
    color: `rgba(15,43,90,0.22)`,
    textTransform: "uppercase" as const,
  },
};


function AnimatedDot({ delay }: { delay: number }) {
  const [opacity, setOpacity] = useState(0.25);

  useEffect(() => {
    let frame: number;
    const start = performance.now() + delay;

    const animate = (now: number) => {
      const t = ((now - start) / 2200) % 1;
      const v = t < 0.5 ? t * 2 : 2 - t * 2;
      setOpacity(0.25 + v * 0.75);
      frame = requestAnimationFrame(animate);
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [delay]);

  return <div style={{ ...styles.dot, opacity }} aria-hidden="true" />;
}

function AnimatedDivider() {
  const [width, setWidth] = useState("0%");

  useEffect(() => {
    const timer = setTimeout(() => setWidth("100%"), 50);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div style={styles.dividerWrap}>
      <div
        style={{
          height: 1,
          background: `rgba(15,43,90,0.2)`,
          width,
          transition: "width 1.4s cubic-bezier(0.77,0,0.18,1)",
        }}
      />
    </div>
  );
}

function AnimatedRing({
  size,
  duration,
  reverse,
}: {
  size: number;
  duration: number;
  reverse?: boolean;
}) {
  const [angle, setAngle] = useState(0);

  useEffect(() => {
    let frame: number;
    let start: number | null = null;
    const dir = reverse ? -1 : 1;

    const animate = (now: number) => {
      if (!start) start = now;
      setAngle(((now - start) / (duration * 1000)) * 360 * dir);
      frame = requestAnimationFrame(animate);
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [duration, reverse]);

  return (
    <div
      aria-hidden="true"
      style={{
        ...styles.ring,
        width: size,
        height: size,
        marginTop: -size / 2,
        marginLeft: -size / 2,
        transform: `rotate(${angle}deg)`,
      }}
    />
  );
}

function FadeUp({
  children,
  delay = 0,
  style,
}: {
  children: React.ReactNode;
  delay?: number;
  style?: React.CSSProperties;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  return (
    <div
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(28px)",
        transition: "opacity 0.85s ease, transform 0.85s ease",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export default function ComingSoon() {
  return (
    <>
      <link
        rel="preconnect"
        href="https://fonts.googleapis.com"
      />
      <link
        href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=DM+Mono:wght@300;400&display=swap"
        rel="stylesheet"
      />

      <main style={styles.wrap} aria-label="Coming soon page">
        {/* Grid lines */}
        <div style={{ ...styles.gridLineH, top: "28%" }} aria-hidden="true" />
        <div style={{ ...styles.gridLineH, bottom: "28%" }} aria-hidden="true" />
        <div style={{ ...styles.gridLineV, left: "18%" }} aria-hidden="true" />
        <div style={{ ...styles.gridLineV, right: "18%" }} aria-hidden="true" />

        {/* Rotating rings */}
        <AnimatedRing size={360} duration={38} />
        <AnimatedRing size={520} duration={54} reverse />



        {/* Label */}
        <FadeUp delay={100}>
          <p style={styles.label}>In Progress</p>
        </FadeUp>

        {/* Title */}
        <FadeUp delay={280} style={{ marginBottom: "2.8rem" }}>
          <div style={styles.titleWrap}>
            <span style={styles.titleOutline}>Coming</span>
            <span style={styles.titleSolid}>Soon</span>
            <span style={styles.titleItalic}>to you.</span>
          </div>
        </FadeUp>

        {/* Divider */}
        <AnimatedDivider />

        {/* Subtitle */}
        <FadeUp delay={650}>
          <p style={styles.sub}>
            This page is being carefully crafted
            <br />
            and will be available in the future.
          </p>
        </FadeUp>

        {/* Pulsing dots */}
        <FadeUp delay={850}>
          <div style={styles.dotsWrap} aria-label="Loading indicator">
            <AnimatedDot delay={0} />
            <AnimatedDot delay={400} />
            <AnimatedDot delay={800} />
          </div>
        </FadeUp>

        {/* Badge */}
        <FadeUp delay={1100} style={{ position: "absolute", bottom: 32, right: 32 }}>
          <span style={styles.badge}>Under Construction</span>
        </FadeUp>
      </main>
    </>
  );
}