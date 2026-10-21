/**
 * Resolve a post-auth destination without allowing protocol-relative or
 * backslash-normalized external origins to escape the current application.
 */
export function safeReturnPath(next, currentOrigin) {
  if (typeof next !== "string" || !next.startsWith("/") || next.startsWith("//")) return "/";
  try {
    const origin = new URL(currentOrigin).origin;
    const destination = new URL(next, origin);
    if (destination.origin !== origin) return "/";
    return `${destination.pathname}${destination.search}${destination.hash}`;
  } catch {
    return "/";
  }
}
