import React from "react";
import {Composition} from "remotion";
import defaultProps from "../props/default-props.json";
import {Test3EpiphanyPoC} from "./Test3EpiphanyPoC";

export const RemotionRoot = () => {
  return (
    <Composition
      id="Test3EpiphanyPoC"
      component={Test3EpiphanyPoC}
      durationInFrames={427}
      fps={30}
      width={1024}
      height={576}
      defaultProps={defaultProps}
    />
  );
};
