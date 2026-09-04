/*
 * Panel accents.
 *
 * STATUS_BAR_COLORS no longer exists: the HUD used to spend a distinct hue on
 * each of eleven navigation entries, which left no colour free to express
 * state and read as a rainbow bookmark bar. Navigation identity is now carried
 * by icon and group (see `layout/StatusBar.vue`); the palette below is only for
 * panel interiors, where an accent per subject aids orientation inside a modal.
 *
 * Values are the "Tinta e Jade" tokens from `styles/tokens.css`.
 */

/** Rarity is real state, so the phenomenon entry keeps a meaningful hue. */
export const PHENOMENON_RARITY_COLORS: Record<string, string> = {
  N: '#9d968a',
  R: '#6fb3a3',
  SR: '#9ccfc1',
  SSR: '#d9b877',
}

export const SHARED_UI_COLORS = {
  textPrimary: '#f2ece0',
  textSecondary: '#cdc6b6',
  textMuted: '#9d968a',
  borderSubtle: '#2b332f',
  surfaceBase: 'rgba(232, 220, 192, 0.04)',
  surfaceRaised: 'rgba(232, 220, 192, 0.07)',
  linkBlue: '#9ccfc1',
  linkBlueHover: '#c4e4dc',
  dangerStrong: '#c0553f',
  dangerSoft: '#d9765e',
  successStrong: '#6fb3a3',
  successSoft: '#9ccfc1',
  warningStrong: '#d9b877',
} as const

/**
 * Per-panel accents. Every entry is drawn from the same three meaning colours
 * (gold = focus, jade = life/water, cinnabar = conflict) plus paper, so panels
 * stay recognisable without reintroducing nine unrelated hues.
 */
export const SYSTEM_PANEL_THEMES = {
  time: {
    accent: '#d9b877',
    accentStrong: '#f3e3bd',
    accentSoft: 'rgba(217, 184, 119, 0.12)',
    title: '#f2ece0',
    empty: '#9d968a',
    border: '#2b332f',
  },
  ranking: {
    accent: '#d9b877',
    accentStrong: '#f3e3bd',
    accentSoft: 'rgba(217, 184, 119, 0.16)',
    link: '#9ccfc1',
    linkHover: '#c4e4dc',
    title: '#ecd6a4',
    empty: '#9d968a',
    border: '#2b332f',
  },
  tournament: {
    accent: '#c0553f',
    accentStrong: '#d9765e',
    accentSoft: 'rgba(192, 85, 63, 0.16)',
    link: '#d9765e',
    linkHover: '#e9a190',
    title: '#d9765e',
    empty: '#9d968a',
    border: '#3a2a26',
  },
  sectRelations: {
    accent: '#6fb3a3',
    accentStrong: '#9ccfc1',
    accentSoft: 'rgba(111, 179, 163, 0.14)',
    link: '#9ccfc1',
    linkHover: '#c4e4dc',
    title: '#9ccfc1',
    empty: '#9d968a',
    border: '#25352f',
  },
  mortal: {
    accent: '#6fb3a3',
    accentStrong: '#9ccfc1',
    accentSoft: 'rgba(111, 179, 163, 0.12)',
    title: '#9ccfc1',
    empty: '#9d968a',
    border: '#25352f',
  },
  dynasty: {
    accent: '#d9b877',
    accentStrong: '#ecd6a4',
    accentSoft: 'rgba(217, 184, 119, 0.14)',
    title: '#ecd6a4',
    empty: '#9d968a',
    border: '#332b1f',
  },
  hiddenDomain: {
    accent: '#8a6f3c',
    accentStrong: '#ecd6a4',
    accentSoft: 'rgba(138, 111, 60, 0.18)',
    title: '#ded7c8',
    empty: '#9d968a',
    border: '#2b332f',
  },
  worldSecret: {
    accent: '#9d968a',
    accentStrong: '#ded7c8',
    accentSoft: 'rgba(232, 220, 192, 0.08)',
    title: '#ded7c8',
    empty: '#9d968a',
    border: '#2b332f',
  },
} as const
