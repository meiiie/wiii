declare module "@shikijs/langs/*" {
  import type { LanguageRegistration } from "shiki";

  const languages: LanguageRegistration[];
  export default languages;
}

declare module "@shikijs/themes/*" {
  import type { ThemeRegistrationAny } from "shiki";

  const theme: ThemeRegistrationAny;
  export default theme;
}
