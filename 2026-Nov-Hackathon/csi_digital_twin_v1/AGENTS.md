# Agent instructions

## Project conventions

- Preserve the repository folder structure. USD files reference other assets by relative paths.
- The README documents Isaac Sim **6.0** as the project-tested version. Do not change versions just because a compute service suggests it; if the user requests another version, treat it as an experiment and report it distinctly from the README baseline.
- The fill station animation uses time codes 1–686 at 30 fps. `FillCam` is a 640 × 480 pinhole camera.
- For station-only work, use `stations/fill_station/fill_station.usda`; the full-line stage is `csi_line.usda`.
- Camera settings and prim paths are in `cameras/<CameraName>.json`.
- Do not overwrite existing preview images unless the user explicitly asks.

## YAAD access

- The YAAD MCP server is configured outside this project, under the user's Copilot configuration. Do not add credentials or machine-specific MCP configuration to this repository.
- Each teammate must use their own YAAD account and registered SSH public key. Never request, print, or commit a private key, passphrase, or bearer token.
- Use YAAD's session/account information to obtain the current user's SSH username and host; do not assume another teammate uses the same username.
- Connect to the CSI network or VPN if YAAD requires it. Check the team's `/workspace` over SSH before uploading files; the team workspace may already contain this project.
- Keep project files under `/workspace` and preserve their relative paths when copying them.
- YAAD batch jobs receive the selected workspace folder as `/job/in` and should write deliverables to `/job/out`.
- Isaac Sim batch jobs require the EULA and privacy-consent environment variables documented in `YAAD-SETUP.md`.
- Before SSH/SCP, confirm the CSI VPN is connected when required. If SSH works but SCP times out, check the active VPN route/interface and bind the transfer to the VPN source address when appropriate; do not assume the transfer failed or retry by changing project files.

## Isaac Sim rendering on YAAD

- Prefer the station stage for a single camera: for `FillCam`, use `/job/in/stations/fill_station/fill_station.usda`, camera prim `/FillStation/FillStation_LocalRoot/FillCam/FillCam`, and the 640 × 480 dimensions from `cameras/FillCam.json`. Use the requested frame within the animation range (1–686).
- The README's `tools/render_example.py` uses PathTracing, but PathTracing stayed black for FillCam on YAAD in the tested setup. A verified frame-600 render used Isaac Sim **6.0.1** with **RayTracedLighting** instead. This is a known successful workaround, not a change to the README's 6.0 baseline; disclose the renderer and version used.
- On a fresh GB10 container, RTX shaders can take several minutes to compile. Set `NVIDIA_DRIVER_CAPABILITIES=all` in addition to `ACCEPT_EULA=Y` and `PRIVACY_CONSENT=Y`. Allow at least 20 minutes for the job and give warm-up up to 600 seconds. Emit flushed progress markers and do not infer a rendering failure from a few initially empty frames.
- After attaching the RGB annotator, warm up by stepping the Replicator orchestrator until `np.asarray(annotator.get_data()).size` is nonzero, with a 600-second timeout. Then perform the requested capture steps (three worked for the verified render) and call `rep.orchestrator.wait_until_complete()` before inspecting saved files.
- A nonempty array or successful job can still contain only black pixels. Before accepting or copying an output, verify that it exists, is a PNG of the requested dimensions, and contains nonblank pixel content (for example, nonzero range/variance). Keep the candidate under `/job/out` and preserve existing previews until these checks pass. YAAD results are available under `/workspace/results/<job-id>/`.
- The 6.0.1 FillCam frame-600 RayTracedLighting capture warmed in about 245 seconds and was verified at 640 × 480. The minimal-scene 6.0.1 warm-up took about 242 seconds. DLSS logged an internal 320 × 240 resolution warning even though the saved PNG was 640 × 480; disabling DLSS was not verified. A viewport capture attempt crashed in headless mode, and a BasicWriter test stalled, so prefer the validated Replicator RGB path unless new evidence supports another method.
- The verified frame-600 image was downloaded after reconnecting to VPN and saved as `previews/fill_cam_frame_600.png`; its pixels and dimensions were checked locally. Do not treat this historical result as proof that a future job or environment will succeed—verify each new output.

## Verification and reporting

- Distinguish a queued, running, failed, and succeeded YAAD job. Do not report a render or other output as complete unless the job succeeded and the output was verified.
- A successful job status alone does not prove an image is valid. Check that the expected output exists and has the expected dimensions before reporting completion.
- Report failures and unverified results explicitly. Do not imply that Isaac Sim rendering on YAAD has been validated by this repository's documentation.
