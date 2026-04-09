import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const cloudLayout = [
  {x: 68, y: 58, size: 28, rotate: -8, delay: 0},
  {x: 188, y: 90, size: 18, rotate: 7, delay: 6},
  {x: 322, y: 52, size: 22, rotate: -4, delay: 12},
  {x: 690, y: 66, size: 20, rotate: 3, delay: 18},
  {x: 840, y: 118, size: 26, rotate: -7, delay: 24},
  {x: 156, y: 188, size: 20, rotate: 5, delay: 30},
  {x: 720, y: 212, size: 19, rotate: -2, delay: 36},
  {x: 126, y: 334, size: 18, rotate: -10, delay: 42},
  {x: 328, y: 286, size: 22, rotate: 8, delay: 48},
  {x: 814, y: 324, size: 24, rotate: -5, delay: 54},
];

const pageLines = [
  "the role of epiphany within narrative forms",
  "significance of insight as a turning point",
  "a sudden intuitive grasp of meaning",
  "moments of clarity, wonder and awakening",
];

const baseFill = {
  width: "100%",
  height: "100%",
  overflow: "hidden",
  fontFamily: "\"Avenir Next\", \"Helvetica Neue\", sans-serif",
};

const center = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const ShadowWord = ({children, style}) => (
  <div
    style={{
      position: "absolute",
      color: "rgba(255, 255, 255, 0.95)",
      textShadow: "0 0 18px rgba(95, 170, 255, 0.35)",
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </div>
);

const NeuralBackdrop = ({frame, palette}) => {
  const glowScale = interpolate(frame, [0, 120], [0.92, 1.08], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        ...baseFill,
        background:
          "radial-gradient(circle at 50% 45%, rgba(165, 220, 255, 0.26) 0%, rgba(20, 28, 66, 0.84) 30%, rgba(7, 8, 20, 1) 72%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: -120,
          background:
            "radial-gradient(circle, rgba(122, 185, 255, 0.55) 0%, rgba(122, 185, 255, 0) 55%)",
          filter: "blur(18px)",
          opacity: 0.75,
          transform: `scale(${glowScale})`,
        }}
      />
      {new Array(14).fill(true).map((_, index) => {
        const rotate = index * 26;
        const pulse = 0.4 + ((index % 5) * 0.08);
        return (
          <div
            key={rotate}
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              width: 2,
              height: 390,
              transform: `translate(-50%, -50%) rotate(${rotate}deg) scaleY(${pulse})`,
              transformOrigin: "center top",
              background:
                "linear-gradient(to bottom, rgba(137, 203, 255, 0.0), rgba(90, 164, 255, 0.65), rgba(137, 203, 255, 0.0))",
              filter: "blur(1px)",
              opacity: 0.78,
            }}
          />
        );
      })}
      {new Array(46).fill(true).map((_, index) => {
        const x = (index * 83) % 1024;
        const y = (index * 57) % 576;
        const twinkle = 0.2 + ((index % 7) * 0.08);
        return (
          <div
            key={`${x}-${y}`}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: 2 + (index % 3),
              height: 2 + (index % 3),
              borderRadius: 999,
              backgroundColor: "rgba(255, 255, 255, 0.8)",
              opacity: twinkle,
              boxShadow: "0 0 8px rgba(140, 210, 255, 0.9)",
            }}
          />
        );
      })}
      <div
        style={{
          position: "absolute",
          left: 452,
          bottom: 36,
          width: 120,
          height: 208,
          background: "linear-gradient(to bottom, rgba(0,0,0,0.96), rgba(0,0,0,1))",
          borderTopLeftRadius: 54,
          borderTopRightRadius: 54,
          borderBottomLeftRadius: 20,
          borderBottomRightRadius: 20,
          opacity: 0.97,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 478,
          bottom: 210,
          width: 68,
          height: 82,
          borderRadius: 999,
          backgroundColor: "rgba(0, 0, 0, 0.98)",
          opacity: 0.97,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 483,
          bottom: 112,
          width: 58,
          height: 102,
          borderRadius: 18,
          border: "1px solid rgba(110, 170, 255, 0.15)",
          backgroundColor: "rgba(12, 20, 45, 0.18)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(to top, ${palette.footerFade} 0%, rgba(0, 0, 0, 0) 44%)`,
        }}
      />
    </AbsoluteFill>
  );
};

const SceneIntro = ({accent, dictionaryTail, questionMark, word}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const titleSpring = spring({
    frame,
    fps,
    config: {damping: 12, stiffness: 110},
  });
  const zoom = interpolate(frame, [0, 105], [1.12, 1], {
    extrapolateRight: "clamp",
  });
  const backgroundShift = interpolate(frame, [0, 105], [24, -12], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        ...baseFill,
        background:
          "radial-gradient(circle at 50% 40%, rgba(255, 244, 209, 0.7) 0%, rgba(255, 255, 255, 0.95) 34%, rgba(244, 241, 234, 1) 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: -40,
          transform: `translateY(${backgroundShift}px) scale(${zoom})`,
          filter: "blur(2px)",
          opacity: 0.52,
        }}
      >
        {pageLines.map((line, index) => (
          <div
            key={line}
            style={{
              fontFamily: "\"Avenir Next\", \"Helvetica Neue\", sans-serif",
              fontSize: 62 - index * 4,
              color: "rgba(28, 28, 28, 0.28)",
              marginTop: 32,
              whiteSpace: "nowrap",
            }}
          >
            {line}
          </div>
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: 840,
          transform: "translate(-50%, -50%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
        }}
      >
        <div
          style={{
            fontSize: 44,
            color: "rgba(0, 0, 0, 0.75)",
            transform: `translateX(${interpolate(frame, [0, 24], [-18, 0])}px)`,
            opacity: interpolate(frame, [0, 18], [0, 1]),
          }}
        >
          the
        </div>
        <div style={{position: "relative"}}>
          <div
            style={{
              position: "absolute",
              left: -14,
              right: -10,
              top: 18,
              bottom: 14,
              backgroundColor: accent,
              opacity: 0.92,
              transform: `scaleX(${titleSpring})`,
              transformOrigin: "left center",
              boxShadow: "0 0 24px rgba(255, 226, 82, 0.35)",
            }}
          />
          <div
            style={{
              position: "relative",
              fontSize: 74,
              fontWeight: 700,
              color: "rgba(24, 24, 24, 0.95)",
              transform: `translateY(${interpolate(frame, [0, 18], [24, 0])}px) scale(${0.92 + titleSpring * 0.08})`,
              opacity: interpolate(frame, [0, 16], [0, 1]),
            }}
          >
            {word}
          </div>
        </div>
        <div
          style={{
            fontSize: 72,
            fontWeight: 700,
            color: questionMark,
            opacity: interpolate(frame, [10, 26], [0, 1]),
            transform: `translateY(${interpolate(frame, [10, 26], [18, 0])}px)`,
          }}
        >
          ?
        </div>
        <div
          style={{
            fontSize: 44,
            color: "rgba(0, 0, 0, 0.65)",
            opacity: interpolate(frame, [16, 36], [0, 1]),
          }}
        >
          {dictionaryTail}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const SceneCloud = ({cloudWords, palette, pronunciation, supportText, word}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = spring({
    frame,
    fps,
    config: {damping: 11, stiffness: 120},
  });

  return (
    <AbsoluteFill style={baseFill}>
      <NeuralBackdrop frame={frame} palette={palette} />
      {cloudLayout.map((layout, index) => (
        <ShadowWord
          key={layout.x}
          style={{
            left: layout.x,
            top: layout.y,
            fontSize: layout.size,
            transform: `rotate(${layout.rotate}deg) translateY(${interpolate(
              frame,
              [layout.delay, layout.delay + 16],
              [20, 0],
              {extrapolateLeft: "clamp"}
            )}px)`,
            opacity: interpolate(frame, [layout.delay, layout.delay + 16], [0, 0.75], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {cloudWords[index % cloudWords.length]}
        </ShadowWord>
      ))}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 168,
          textAlign: "center",
          transform: `scale(${0.9 + reveal * 0.1})`,
        }}
      >
        <div
          style={{
            fontSize: 70,
            fontWeight: 700,
            color: palette.accent,
            textShadow: `0 0 22px ${palette.accentGlow}`,
            opacity: interpolate(frame, [6, 22], [0, 1]),
          }}
        >
          {word}
        </div>
        <div
          style={{
            marginTop: 6,
            fontFamily: "\"Iowan Old Style\", \"Times New Roman\", serif",
            fontSize: 32,
            fontStyle: "italic",
            color: "rgba(255, 236, 150, 0.92)",
            opacity: interpolate(frame, [14, 30], [0, 1]),
          }}
        >
          {pronunciation}
        </div>
        <div
          style={{
            marginTop: 16,
            fontSize: 22,
            color: "rgba(236, 242, 255, 0.8)",
            letterSpacing: 0.5,
            opacity: interpolate(frame, [20, 42], [0, 1]),
          }}
        >
          {supportText}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const SceneFinale = ({definition, finalWord, palette, pronunciation}) => {
  const frame = useCurrentFrame();
  const titleLift = interpolate(frame, [0, 36], [30, 0], {
    extrapolateRight: "clamp",
  });
  const titleOpacity = interpolate(frame, [0, 28], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={baseFill}>
      <NeuralBackdrop frame={frame} palette={palette} />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 116,
          textAlign: "center",
          transform: `translateY(${titleLift}px)`,
          opacity: titleOpacity,
        }}
      >
        <div
          style={{
            fontSize: 74,
            fontWeight: 800,
            color: "#ffffff",
            letterSpacing: 2,
            WebkitTextStroke: "4px #2a63ff",
            textShadow:
              "0 0 30px rgba(130, 180, 255, 0.35), 0 6px 16px rgba(0, 0, 0, 0.3)",
          }}
        >
          {finalWord}
        </div>
        <div
          style={{
            marginTop: 18,
            fontFamily: "\"Iowan Old Style\", \"Times New Roman\", serif",
            fontSize: 26,
            fontStyle: "italic",
            color: "rgba(255, 244, 190, 0.92)",
          }}
        >
          {pronunciation}
        </div>
        <div
          style={{
            marginTop: 14,
            fontSize: 28,
            color: palette.definition,
            fontWeight: 600,
            textShadow: "0 0 18px rgba(255, 216, 84, 0.12)",
          }}
        >
          {definition}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const Test3EpiphanyPoC = ({
  audioFile,
  cloudWords,
  definition,
  dictionaryTail,
  finalWord,
  palette,
  pronunciation,
  questionMark,
  supportText,
  word,
}) => {
  return (
    <AbsoluteFill style={{...baseFill, backgroundColor: "#05070f"}}>
      <Audio src={staticFile(audioFile)} volume={0.85} />
      <Sequence from={0} durationInFrames={108}>
        <SceneIntro
          accent={palette.accent}
          dictionaryTail={dictionaryTail}
          questionMark={questionMark}
          word={word}
        />
      </Sequence>
      <Sequence from={108} durationInFrames={146}>
        <SceneCloud
          cloudWords={cloudWords}
          palette={palette}
          pronunciation={pronunciation}
          supportText={supportText}
          word={word}
        />
      </Sequence>
      <Sequence from={254} durationInFrames={173}>
        <SceneFinale
          definition={definition}
          finalWord={finalWord}
          palette={palette}
          pronunciation={pronunciation}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
