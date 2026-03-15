import { defaultSchema } from "rehype-sanitize";

export const baseSanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames || []),
    "mark", "del", "ins",
  ],
  attributes: {
    ...defaultSchema.attributes,
    div: [...(defaultSchema.attributes?.div || []), "className", "style"],
    span: [...(defaultSchema.attributes?.span || []), "className", "style", "aria-hidden"],
  },
};

export const mathSanitizeSchema = {
  ...baseSanitizeSchema,
  tagNames: [
    ...(baseSanitizeSchema.tagNames || []),
    "math", "semantics", "mrow", "mi", "mn", "mo", "mover", "munder", "munderover",
    "msup", "msub", "msubsup", "mfrac", "msqrt", "mroot", "mtable",
    "mtr", "mtd", "mtext", "mspace", "annotation", "mpadded", "menclose",
  ],
  attributes: {
    ...baseSanitizeSchema.attributes,
    math: ["xmlns", "display"],
    annotation: ["encoding"],
  },
};
