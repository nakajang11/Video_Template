import React from "react";
import {Composition} from "remotion";
import defaultProps from "../props/default-props.json";
import {Test2QuoteTemplate} from "./Test2QuoteTemplate";

export const RemotionRoot = () => {
  return (
    <Composition
      id="Test2QuoteTemplate"
      component={Test2QuoteTemplate}
      durationInFrames={1349}
      fps={30}
      width={1280}
      height={720}
      defaultProps={defaultProps}
    />
  );
};
