# W4 · VIDEO KIT (agent: ui-builder, main branch after W3 merge, ~45 min)

Mission: a repeatable, scripted recording of the demo so the video can be re-shot in 3 minutes after any fix, plus captions and an ffmpeg pipeline. Humans can still record manually with the same beat sheet; this is the safety net and the way to get a clean take.

Read first: `docs/DEMO_SCRIPT.md` (beat list with timings and captions), `docs/handoff/wow-ui.md`.
You own: `web/scripts/record_demo.mjs`, `scripts/make_video.sh`, `docs/video/`.

## Steps
1. **Beat file** `web/scripts/beats.json`: an array of `{t_ms, action, args, caption}` mirroring the beat list in `docs/DEMO_SCRIPT.md` (actions: `goto`, `click`, `hover`, `wait`, `type`, `press`, `scroll`). One source of truth: `record_demo.mjs` and the caption generator both read it.
2. **Recorder** `web/scripts/record_demo.mjs` (Playwright chromium): viewport 1920x1080, `recordVideo: {dir: 'docs/video', size: {width: 1920, height: 1080}}`, reduced-motion OFF, a fake cursor (an absolutely positioned div following `mousemove`, 24 px, ring + dot, with easing) because Playwright videos have no cursor, smooth mouse moves with `page.mouse.move(x, y, {steps: 25})`, waits between beats from the file. Fails loudly if any selector is missing. Starts the API/web via env `BASE_URL` (default http://localhost:5173) and requires `VITE_API=live`. Output `docs/video/raw.webm`.
3. **Captions** `scripts/make_captions.py`: `beats.json` -> `docs/video/captions.srt` (max 2 lines, 42 chars per line, shown 0.2 s after the beat starts, at least 1.6 s on screen).
4. **Compose** `scripts/make_video.sh`: `ffmpeg -y -i docs/video/raw.webm -vf "subtitles=docs/video/captions.srt:force_style='Fontname=Helvetica,Fontsize=22,Outline=2,Shadow=0,MarginV=48'" -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -movflags +faststart docs/video/plumb.mp4`. If `docs/video/music.mp3` exists mix it at -22 dB; if `docs/video/vo.m4a` exists mix it on top with `amix`. Check `ffmpeg -version` first and print `brew install ffmpeg` if missing. Also produce `docs/video/plumb-60s.mp4` from the cut list in `docs/DEMO_SCRIPT.md` ("60-second cut") using `-ss/-t` segments and `concat`.
5. **Poster frame**: export frame at the end of the hook (`-ss 00:00:09`) as `docs/video/poster.png` (for the submission thumbnail).
6. Run it once end to end against the live API (`make api` + `make web` running) and LOOK at three extracted frames (downscaled) to confirm the beats are on screen. Fix timing drift by editing `beats.json` only.

## Gates
```
cd web && node scripts/record_demo.mjs && cd ..
.venv/bin/python scripts/make_captions.py && bash scripts/make_video.sh
ls -l docs/video/plumb.mp4 docs/video/plumb-60s.mp4 docs/video/poster.png
```
Video length must be between 85 and 110 s (check with `ffprobe -v error -show_entries format=duration -of csv=p=0`).

## Don'ts
No on-screen numbers that are not produced by the live app. No third-party logos or music you do not have the right to use (use silence or a royalty-free track you can credit). Do not edit app code to make the recording work; if a selector is missing, fix `beats.json` or write the defect into the handoff.

## Handoff
`docs/handoff/video-kit.md`: how to re-record in one command, how to add voiceover, known timing sensitivities.
