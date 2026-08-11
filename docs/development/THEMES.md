# Linlin UI Themes

Linlin provides six global product themes from the selector in the top bar:

| Theme | UI label | Intended use |
| --- | --- | --- |
| Light | 明亮 | Neutral daylight workspace |
| Dark | 黑暗 | Low-light, high-focus workspace |
| Ocean | 海洋 | Cool blue-green dark palette |
| Forest | 森林 | Calm green dark palette |
| Twilight | 暮光 | Purple evening palette |
| Warm Sand | 暖沙 | Warm, low-glare light palette |

The selected value is stored as the non-secret `linlin-theme` browser preference.
An absent or invalid value safely falls back to Light. Applying a theme sets only
document presentation state; it does not alter runtime, model, provider, training,
credential, workspace, or API behavior.

## Design token coverage

Shared tokens control the page, navigation, top bar, surfaces, borders, text,
inputs, buttons, chat bubbles, Code previews, training charts, state banners,
focus outlines, and responsive navigation. Every palette defines readable page
and foreground colors, while the existing reduced-motion and mobile rules remain
in effect.

## Verification

- Select each of the six options and confirm its distinct page and foreground palette.
- Reload the page and confirm that the selected option remains active.
- Check Overview and Chat at desktop width, including inputs, warnings, and navigation.
- Run the frontend build and lint, backend regression suite, and desktop Cargo check.
