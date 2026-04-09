import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const baseFill = {
  width: "100%",
  height: "100%",
  overflow: "hidden",
  fontFamily: "\"Avenir Next\", \"Helvetica Neue\", sans-serif",
};

const footerStyle = {
  position: "absolute",
  left: 0,
  right: 0,
  bottom: 0,
  height: 52,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 28,
  fontWeight: 700,
};

const MediaBackdrop = ({asset, style}) => {
  if (!asset?.src) {
    return null;
  }

  const sharedStyle = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: asset.objectFit ?? "cover",
    ...style,
  };

  if (asset.kind === "video") {
    return (
      <OffthreadVideo
        src={staticFile(asset.src)}
        muted
        volume={0}
        style={sharedStyle}
      />
    );
  }

  return <Img src={staticFile(asset.src)} style={sharedStyle} />;
};

const MemoryFooter = ({background, color, text}) => (
  <div
    style={{
      ...footerStyle,
      background,
      color,
    }}
  >
    {text}
  </div>
);

const IntroScene = ({asset, intro, palette, sceneFrames, transitionOutFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = spring({
    frame,
    fps,
    config: {damping: 13, stiffness: 110},
  });
  const exitOpacity = interpolate(
    frame,
    [sceneFrames - transitionOutFrames, sceneFrames],
    [1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"}
  );
  const zoom = interpolate(frame, [0, sceneFrames], [1.08, 1], {
    extrapolateRight: "clamp",
  });
  const driftY = interpolate(frame, [0, sceneFrames], [14, -10], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{...baseFill, opacity: exitOpacity}}>
      <MediaBackdrop
        asset={asset}
        style={{
          transform: `scale(${zoom}) translateY(${driftY}px)`,
          filter: "blur(2px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 50% 42%, rgba(255,255,255,0.26) 0%, rgba(255,255,255,0.18) 34%, rgba(241,239,232,0.10) 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          transform: "translate(-50%, -50%)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            fontSize: 44,
            color: "rgba(0, 0, 0, 0.8)",
            opacity: interpolate(frame, [0, 18], [0, 1]),
            transform: `translateX(${interpolate(frame, [0, 22], [-20, 0])}px)`,
          }}
        >
          {intro.preWord}
        </div>
        <div style={{position: "relative"}}>
          <div
            style={{
              position: "absolute",
              left: -12,
              right: -8,
              top: 14,
              bottom: 10,
              backgroundColor: palette.introHighlight,
              boxShadow: `0 0 24px ${palette.introGlow}`,
              opacity: 0.96,
              transform: `scaleX(${reveal})`,
              transformOrigin: "left center",
            }}
          />
          <div
            style={{
              position: "relative",
              fontSize: 84,
              fontWeight: 700,
              color: "rgba(18, 18, 18, 0.95)",
              letterSpacing: -2,
              opacity: interpolate(frame, [0, 16], [0, 1]),
              transform: `translateY(${interpolate(frame, [0, 16], [22, 0])}px) scale(${0.94 + reveal * 0.06})`,
            }}
          >
            {intro.word}
          </div>
        </div>
        <div
          style={{
            fontSize: 82,
            fontWeight: 700,
            color: intro.questionMarkColor,
            opacity: interpolate(frame, [10, 26], [0, 1]),
            transform: `translateY(${interpolate(frame, [10, 26], [24, 0])}px)`,
          }}
        >
          ?
        </div>
      </div>
    </AbsoluteFill>
  );
};

const CloudEntry = ({entry, layout}) => {
  const frame = useCurrentFrame();
  const delay = layout.delay ?? 0;
  const rise = interpolate(frame, [delay, delay + 16], [16, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(frame, [delay, delay + 16], [0, 0.95], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        left: layout.x,
        top: layout.y,
        width: layout.width ?? 192,
        opacity,
        transform: `translateY(${rise}px) rotate(${layout.rotate ?? 0}deg)`,
        color: "#ffffff",
        textAlign: "center",
        textShadow: "0 0 18px rgba(95, 170, 255, 0.34)",
      }}
    >
      <div style={{fontSize: 32, fontWeight: 700, lineHeight: 1.05}}>
        {entry.term}
      </div>
      <div
        style={{
          marginTop: 2,
          fontFamily: "\"Iowan Old Style\", \"Times New Roman\", serif",
          fontSize: 18,
          fontStyle: "italic",
          color: "rgba(255, 245, 183, 0.95)",
        }}
      >
        {entry.pronunciation}
      </div>
      <div
        style={{
          marginTop: 4,
          fontSize: 18,
          color: "rgba(245, 247, 255, 0.88)",
          lineHeight: 1.2,
        }}
      >
        {entry.definition}
      </div>
    </div>
  );
};

const CloudScene = ({
  asset,
  cloud,
  palette,
  sceneFrames,
  transitionInFrames,
  transitionOutFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = spring({
    frame,
    fps,
    config: {damping: 11, stiffness: 120},
  });
  const inOpacity = interpolate(frame, [0, transitionInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const outOpacity = interpolate(
    frame,
    [sceneFrames - transitionOutFrames, sceneFrames],
    [1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"}
  );
  const opacity = Math.min(inOpacity, outOpacity);
  const scale = interpolate(frame, [0, sceneFrames], [1.03, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{...baseFill, opacity}}>
      <MediaBackdrop
        asset={asset}
        style={{
          transform: `scale(${scale})`,
          filter: "blur(0.4px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 50% 48%, rgba(0,0,0,0.02) 0%, rgba(2,4,16,0.12) 42%, rgba(0,0,0,0.34) 100%)",
        }}
      />
      {cloud.entryLayout.map((layout, index) => (
        <CloudEntry
          key={`${layout.x}-${layout.y}`}
          entry={cloud.entries[index % cloud.entries.length]}
          layout={layout}
        />
      ))}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 182,
          textAlign: "center",
          transform: `scale(${0.92 + reveal * 0.08})`,
        }}
      >
        <div
          style={{
            fontSize: 72,
            fontWeight: 700,
            color: palette.accent,
            textShadow: `0 0 24px ${palette.accentGlow}`,
            opacity: interpolate(frame, [6, 22], [0, 1]),
          }}
        >
          {cloud.word}
        </div>
        <div
          style={{
            marginTop: 4,
            fontFamily: "\"Iowan Old Style\", \"Times New Roman\", serif",
            fontSize: 36,
            fontStyle: "italic",
            color: "rgba(255, 240, 165, 0.95)",
            opacity: interpolate(frame, [10, 26], [0, 1]),
          }}
        >
          {cloud.pronunciation}
        </div>
        <div
          style={{
            marginTop: 8,
            fontSize: 30,
            fontWeight: 600,
            color: palette.subtitle,
            opacity: interpolate(frame, [14, 30], [0, 1]),
          }}
        >
          {cloud.definition}
        </div>
      </div>
      <MemoryFooter
        background={palette.footerBackground}
        color={palette.footerText}
        text={cloud.memoryScore}
      />
    </AbsoluteFill>
  );
};

const FinaleScene = ({asset, finale, palette, sceneFrames, transitionInFrames}) => {
  const frame = useCurrentFrame();
  const inOpacity = interpolate(frame, [0, transitionInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleLift = interpolate(frame, [0, 36], [28, 0], {
    extrapolateRight: "clamp",
  });
  const bodyOpacity = interpolate(frame, [16, 48], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scale = interpolate(frame, [0, sceneFrames], [1.02, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{...baseFill, opacity: inOpacity}}>
      <MediaBackdrop
        asset={asset}
        style={{
          transform: `scale(${scale})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 50% 24%, rgba(112, 173, 255, 0.14) 0%, rgba(0, 0, 0, 0) 34%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 84,
          textAlign: "center",
          transform: `translateY(${titleLift}px)`,
          opacity: interpolate(frame, [0, 28], [0, 1]),
        }}
      >
        <div
          style={{
            fontSize: 108,
            fontWeight: 800,
            color: "#ffffff",
            letterSpacing: 1,
            WebkitTextStroke: `4px ${palette.titleStroke}`,
            textShadow:
              `0 0 28px ${palette.titleGlow}, 0 6px 16px rgba(0, 0, 0, 0.34)`,
          }}
        >
          {finale.finalWord}
        </div>
        <div
          style={{
            marginTop: 8,
            fontFamily: "\"Iowan Old Style\", \"Times New Roman\", serif",
            fontSize: 30,
            fontStyle: "italic",
            color: palette.accent,
          }}
        >
          {finale.pronunciation}
        </div>
        <div
          style={{
            marginTop: 14,
            fontSize: 32,
            fontStyle: "italic",
            color: palette.subtitle,
          }}
        >
          {finale.definition}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 80,
          right: 80,
          top: 322,
          opacity: bodyOpacity,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            minWidth: 94,
            padding: "6px 12px",
            borderRadius: 10,
            backgroundColor: palette.exampleAccent,
            color: "#111111",
            fontSize: 28,
            fontWeight: 700,
          }}
        >
          {finale.exampleLabel}
        </div>
        <div
          style={{
            marginTop: 18,
            fontSize: 36,
            fontWeight: 700,
            color: "#f5f5f5",
            lineHeight: 1.25,
          }}
        >
          {finale.exampleEn}
        </div>
        <div
          style={{
            marginTop: 12,
            fontSize: 28,
            fontWeight: 700,
            color: palette.exampleTranslation,
            lineHeight: 1.25,
          }}
        >
          {finale.exampleVi}
        </div>
      </div>
      <MemoryFooter
        background={palette.footerBackground}
        color={palette.footerText}
        text={finale.memoryScore}
      />
    </AbsoluteFill>
  );
};

const IntroToCloudTransition = ({config}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(
    frame,
    [config.startFrame, config.startFrame + config.durationFrames],
    [0, 1],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"}
  );

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        opacity: progress,
        background:
          "radial-gradient(circle at 50% 50%, rgba(255,255,255,0.0) 0%, rgba(18,20,54,0.22) 44%, rgba(5,7,14,0.72) 100%)",
      }}
    />
  );
};

const CloudToFinaleTransition = ({config, footerBackground}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(
    frame,
    [config.startFrame, config.startFrame + config.durationFrames],
    [0, 1],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"}
  );
  const cardY = interpolate(progress, [0, 1], [120, 0]);

  return (
    <AbsoluteFill style={{pointerEvents: "none", opacity: progress}}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.0) 0%, rgba(0,0,0,0.68) 72%, rgba(0,0,0,0.98) 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          transform: `translateY(${cardY}px)`,
          background:
            "radial-gradient(circle at 50% 24%, rgba(112,173,255,0.12) 0%, rgba(0,0,0,0) 34%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 52,
          background: footerBackground,
        }}
      />
    </AbsoluteFill>
  );
};

export const Test3GlossaryTemplate = ({
  audioFile,
  cloud,
  finale,
  intro,
  mediaInputs,
  palette,
  transitions,
}) => {
  return (
    <AbsoluteFill style={{...baseFill, backgroundColor: "#05070f"}}>
      <Audio src={staticFile(audioFile)} volume={0.85} />
      <Sequence from={0} durationInFrames={108}>
        <IntroScene
          asset={mediaInputs.introBackground}
          intro={intro}
          palette={palette}
          sceneFrames={108}
          transitionOutFrames={transitions.introToCloud.durationFrames}
        />
      </Sequence>
      <Sequence from={96} durationInFrames={158}>
        <CloudScene
          asset={mediaInputs.cloudBackground}
          cloud={cloud}
          palette={palette}
          sceneFrames={158}
          transitionInFrames={transitions.introToCloud.durationFrames}
          transitionOutFrames={transitions.cloudToFinale.durationFrames}
        />
      </Sequence>
      <Sequence from={244} durationInFrames={183}>
        <FinaleScene
          asset={mediaInputs.finaleBackground}
          finale={finale}
          palette={palette}
          sceneFrames={183}
          transitionInFrames={transitions.cloudToFinale.durationFrames}
        />
      </Sequence>
      <IntroToCloudTransition config={transitions.introToCloud} />
      <CloudToFinaleTransition
        config={transitions.cloudToFinale}
        footerBackground={palette.footerBackground}
      />
    </AbsoluteFill>
  );
};
