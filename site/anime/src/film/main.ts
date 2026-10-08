import "@fontsource/anton/latin-400.css";
import "@fontsource/dm-mono/400.css";
import "@fontsource/instrument-sans/400.css";
import "@fontsource/instrument-serif/400.css";
import "../style.css";
import { hasWebGL2 } from "./capable";
import { startFilm } from "./engine";

if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !hasWebGL2()) {
  window.location.replace("/?page=dom");
} else {
  document.documentElement.classList.add("is-film");
  void startFilm();
}
