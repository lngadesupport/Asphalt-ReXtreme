# 1.0 Installer UI specification

## Composition

The installer uses the user-approved reference layout:

- left: vertical trailer panel;
- right/top: the official Asphalt ReXtreme logo in the position previously occupied by the textual title;
- right/middle: installation status and progress;
- right/bottom: primary action button and secondary controls.

## Opening animation

Target sequence:

```
0.0s  window/background
0.2s  base chrome visible
0.2s  logo fade begins
1.1s  logo reaches full opacity
0.45s trailer fade begins
1.65s trailer reaches full opacity
0.9s  status/actions fade in
~1.7s interface fully settled
```

Transitions use cubic ease-out rather than linear stepping.

## Logo

- source: project-owner supplied transparent PNG;
- same position as the former `Asphalt ReXtreme Offline` title;
- fade-in ~900 ms;
- no bouncing or exaggerated motion;
- optional very subtle glow only.

## Trailer

- source: project-owner supplied Asphalt Xtreme trailer;
- original source is horizontal; installer media is rendered to a vertical panel;
- center crop with slight zoom;
- loop continuously;
- starts muted;
- fade-in ~1200 ms;
- no visible black bars;
- loop boundary should be visually unobtrusive.

For maximum Windows LTSC reliability, the installer may ship a pre-rendered silent vertical media asset rather than requiring a browser or third-party codec runtime.

## Motion

- status cross-fade: 500–700 ms;
- button hover: 150–220 ms;
- progress bar: continuously interpolated to measured install progress;
- completion state fades in rather than replacing the whole window abruptly.

## Completion

Final state presents:
- installation completed;
- `JOGAR AGORA` primary button;
- optional create-desktop-shortcut state;
- no console window.
