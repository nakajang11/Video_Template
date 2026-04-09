import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

const baseFill = {
  width: "100%",
  height: "100%",
  overflow: "hidden",
  fontFamily: "\"Times New Roman\", Georgia, serif",
};

const AssetImage = ({src, style}) => {
  if (!src) {
    return null;
  }

  return (
    <Img
      src={staticFile(src)}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        objectFit: "cover",
        ...style,
      }}
    />
  );
};

const BackgroundLayer = ({backgrounds, fadeDuration}) => {
  const frame = useCurrentFrame();

  return (
    <>
      {backgrounds.map((background, index) => {
        const fadeInStart = background.startFrame - fadeDuration;
        const fadeInEnd = background.startFrame;
        const fadeOutStart = background.endFrame - fadeDuration;
        const fadeOutEnd = background.endFrame;

        const fadeIn =
          index === 0
            ? 1
            : interpolate(frame, [fadeInStart, fadeInEnd], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });

        const fadeOut =
          index === backgrounds.length - 1
            ? 1
            : interpolate(frame, [fadeOutStart, fadeOutEnd], [1, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });

        const opacity = Math.min(fadeIn, fadeOut);
        const localFrame = Math.max(0, frame - background.startFrame);
        const driftScale = interpolate(
          localFrame,
          [0, Math.max(1, background.endFrame - background.startFrame)],
          [1.04, 1],
          {extrapolateRight: "clamp"}
        );

        return (
          <AssetImage
            key={background.src}
            src={background.src}
            style={{
              opacity,
              transform: `scale(${driftScale})`,
            }}
          />
        );
      })}
    </>
  );
};

const KnightLayer = ({overlay}) => {
  const frame = useCurrentFrame();
  const bobY = interpolate(frame, [0, 1349], [8, -4], {
    extrapolateRight: "clamp",
  });

  return (
    <AssetImage
      src={overlay.src}
      style={{
        inset: "auto",
        left: "50%",
        bottom: -18,
        width: overlay.width ?? 360,
        height: "auto",
        transform: `translateX(-50%) translateY(${bobY}px)`,
        objectFit: "contain",
      }}
    />
  );
};

const WordLayer = ({wordBeats, textStyle}) => {
  const frame = useCurrentFrame();

  return (
    <>
      {wordBeats.map((beat, index) => {
        const opacity = interpolate(
          frame,
          [beat.startFrame, beat.startFrame + 10, beat.endFrame - 10, beat.endFrame],
          [0, 1, 1, 0],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }
        );

        const lift = interpolate(
          frame,
          [beat.startFrame, beat.startFrame + 14],
          [18, 0],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }
        );

        return (
          <div
            key={`${beat.text}-${index}`}
            style={{
              position: "absolute",
              left: "50%",
              top: beat.top ?? 185,
              transform: `translateX(-50%) translateY(${lift}px)`,
              opacity,
              fontSize: beat.fontSize ?? textStyle.fontSize,
              fontWeight: 700,
              color: textStyle.color,
              textShadow: `0 3px 0 ${textStyle.shadowColor}`,
              letterSpacing: textStyle.letterSpacing,
              whiteSpace: "nowrap",
            }}
          >
            {beat.text}
          </div>
        );
      })}
    </>
  );
};

const CurtainReveal = ({durationFrames}) => {
  const frame = useCurrentFrame();
  const height = interpolate(frame, [0, durationFrames], [320, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 0,
          height,
          backgroundColor: "#000000",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height,
          backgroundColor: "#000000",
        }}
      />
    </>
  );
};

export const Test2QuoteTemplate = ({
  audioFile,
  mediaInputs,
  textStyle,
  transitions,
  wordBeats,
}) => {
  return (
    <AbsoluteFill style={{...baseFill, backgroundColor: "#000000"}}>
      <Audio src={staticFile(audioFile)} volume={0.85} />
      <BackgroundLayer
        backgrounds={mediaInputs.backgrounds}
        fadeDuration={transitions.backgroundFade.durationFrames}
      />
      <KnightLayer overlay={mediaInputs.knightOverlay} />
      <WordLayer wordBeats={wordBeats} textStyle={textStyle} />
      <CurtainReveal durationFrames={transitions.curtainReveal.durationFrames} />
    </AbsoluteFill>
  );
};
