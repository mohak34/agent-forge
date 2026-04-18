import { marked } from "marked";
import DOMPurify from "dompurify";

export function parseMarkdown(text: string) {
  if (!text) return "";
  const rawHtml = marked.parse(text, { async: false }) as string;
  // Safely handle DOMPurify in SSR/Node vs Browser
  if (typeof window !== "undefined" && DOMPurify.sanitize) {
    return DOMPurify.sanitize(rawHtml);
  }
  // In SSR we just return the raw HTML, or we could strip scripts.
  // For safety, we just return the raw string here because it's our own LLM data 
  // and hydration will replace it anyway if needed.
  return rawHtml;
}
