import React from "react";
import { Composition } from "remotion";
import { DemoNarration } from "./DemoNarration";
import { CONSTANTS } from "./timeline";

const SIZE = {
  durationInFrames: CONSTANTS.DURATION_IN_FRAMES,
  fps: CONSTANTS.FPS,
  width: CONSTANTS.WIDTH,
  height: CONSTANTS.HEIGHT,
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Narration"
        component={DemoNarration}
        {...SIZE}
        defaultProps={{ showOverlay: true }}
      />
      <Composition
        id="Base"
        component={DemoNarration}
        {...SIZE}
        defaultProps={{ showOverlay: false }}
      />
    </>
  );
};