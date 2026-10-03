/**
 * Note: When using the Node.JS APIs, the config file
 * doesn't apply. Instead, pass options directly to the APIs.
 *
 * All configuration options: https://remotion.dev/docs/config
 *
 * Deliberately almost empty. The delivery encode is done by
 * scripts/finalize.mjs with ffmpeg, because Remotion's own encoder always tags
 * its output full-range yuvj420p. What is left here is bundling only.
 */

import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);