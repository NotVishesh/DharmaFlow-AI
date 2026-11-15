# Revised execution specification: DharmaFlow motion video

This specification supersedes the still-image and placeholder allowances in the original master prompt.

Build and maintain the existing Electron / React / FastAPI application under dharmaflow-one. Preserve existing projects. Default to local video generation, with an explicitly configured paid API fallback.

1. Production output must originate from a text-to-video model generating temporal frames. Prohibit image zoom/pan, looping a still, procedural title cards, stock footage substitution, and mock audio or scripts. Missing services must produce actionable errors.
2. Use local Wan 2.1 1.3B with sequential CPU offload and tiled VAE decoding on constrained GPUs. Do not promise successful 6 GB inference until measured. Report native resolution separately from export dimensions. Provide optional fal Wan 2.2 at 720p, enabled only through backend configuration.
3. Produce a coherent script and a shot-by-shot storyboard describing visible physical action, environmental movement, camera, composition and lighting. Preserve every approved narration word. Do not force every topic into a space or cartoon template. Retain editable Review and automatic Turbo modes.
4. Synthesize real narration first, measure it, add 300 ms breathing room and quantize scene boundaries to 30 fps. Split long scenes into additional generated shots; never stretch, cut narration, or loop insufficient footage to fill time.
5. Validate generated footage before export: decodable video, multiple frames, sufficient duration and measurable visual changes. A change detector cannot prove semantic action or artistic merit; keep human preview review.
6. Export a continuous H.264/AAC timeline at 1080 × 1920 / 30 fps with clear upscaling disclosure. Normalize speech loudness. Reject exports with missing streams or more than 50 ms start/end offset. Test decoded audio at scene boundaries, not only container durations.
7. Save an export quality report containing per-scene timing, final timing, provider, native resolution and test-mode marker. Display this report in the preview. Do not claim lip-sync: narration alignment is distinct from facial speech animation.
8. Setup readiness must reflect real video weights and services. Download weights resumably, verify hashes, expose failures. Never populate fake production model artifacts or report readiness from mock flags. Keep credentials on the backend.
9. Do not publish automatically. Preserve user review and explicit YouTube upload. Preserve backend errors and prevent out-of-state review requests.
10. Run backend media/provider/state tests, frontend typechecking, desktop build and browser workflow tests. Keep tests isolated from user projects. Clearly distinguish mocked workflow tests from live model and publication tests. A live quality acceptance test requires a real generated sample viewed by a person; do not substitute synthetic test footage as proof.

Acceptance scene: a small fox trots through a sunlit forest, steps over a mossy log, and shakes falling leaves from its fur. Leaves and fur must move independently of the camera. Narration must remain complete and aligned with the intended shot. Inspect the complete exported video and its timing report.

## Connected long-form generation
Default to a 60-second film composed of 12 connected five-second story beats. Offer 15/30/60/120-second targets. Create a beginning, development and resolution with concrete actions and shared visual character/setting descriptions in every shot. Preserve approved narration verbatim. Generate new footage for every beat, measure speech before rendering, extend duration when speech requires it, and concatenate all scenes into one synchronized export. Disclose local rendering time and the limits of text-only character continuity.
