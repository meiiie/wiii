/**
 * Plate widths live in the markup, including 1920 and 2560.
 * Do not probe those files: a probe downloads them on every visit,
 * including the 2560s the preload deliberately leaves out.
 * Shard backgrounds are chosen in CSS so a decorative shatter can
 * share the impact plate the picture element already requested.
 */

export function upgradeArt(): void {
  /* widths are in index.html */
}
