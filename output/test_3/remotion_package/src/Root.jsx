import React from "react";
import {Composition} from "remotion";
import defaultProps from "../props/default-props.json";
import {Test3GlossaryTemplate} from "./Test3GlossaryTemplate";

export const RemotionRoot = () => {
  return (
    <Composition
      id="Test3GlossaryTemplate"
      component={Test3GlossaryTemplate}
      durationInFrames={427}
      fps={30}
      width={1024}
      height={576}
      defaultProps={defaultProps}
    />
  );
};
