/**
 * Input validation utilities.
 *
 * Provides basic validation for email addresses, Turkish mobile phone
 * numbers, and URLs. All functions return a boolean so callers decide how
 * to handle invalid input.
 */

/**
 * Validate a basic email address.
 *
 * Local part: alphanumerics plus `.`, `_`, `%`, `+`, `-`.
 * Domain part: at least two dot-separated labels; each label is alphanumeric
 * with optional internal hyphens.
 *
 * @param str - the string to validate
 * @returns true when the string looks like a valid email address
 */
export function isEmail(str: string): boolean {
  if (typeof str !== "string" || str.length === 0) return false;

  const atIndex = str.indexOf("@");
  // exactly one @, and it must not be first or last
  if (atIndex < 1 || atIndex !== str.lastIndexOf("@")) return false;

  const localPart = str.slice(0, atIndex);
  const domainPart = str.slice(atIndex + 1);
  if (localPart.length === 0 || domainPart.length === 0) return false;

  if (!/^[a-zA-Z0-9._%+-]+$/.test(localPart)) return false;

  // Domain requires at least one dot, no leading/trailing/consecutive dots
  if (
    !domainPart.includes(".") ||
    domainPart.startsWith(".") ||
    domainPart.endsWith(".") ||
    domainPart.includes("..")
  ) {
    return false;
  }

  for (const label of domainPart.split(".")) {
    if (label.length === 0) return false;
    if (!/^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$/.test(label)) return false;
  }

  return true;
}

/**
 * Validate a Turkish mobile phone number.
 *
 * Accepts `05xx xxx xx xx` with optional `+90`/`0` country-code prefix.
 * Spaces, dashes, and parentheses around the country code are allowed.
 *
 * @param str - the string to validate
 * @returns true when the string looks like a valid Turkish mobile number
 */
export function isPhone(str: string): boolean {
  if (typeof str !== "string" || str.length === 0) return false;

  // Strip spaces, dashes, and parentheses so formats like
  // "+90 (532) 123 45 67" are accepted.
  const normal = str.replace(/[\s()-]/g, "");

  // Turkish mobile numbers: national 05xx... (trunk prefix 0) or
  // international +90 5xx... — the trunk prefix is required.
  return /^(?:\+90|0)5\d{9}$/.test(normal);
}

/**
 * Validate a basic URL.
 *
 * Accepts `http://` or `https://` followed by a valid host (domain or IPv4),
 * with optional port, path, query string, and fragment.
 *
 * @param str - the string to validate
 * @returns true when the string looks like a valid URL
 */
export function isUrl(str: string): boolean {
  if (typeof str !== "string" || str.length === 0) return false;

  if (!str.startsWith("http://") && !str.startsWith("https://")) return false;

  const rest = str.slice(str.indexOf("://") + 3);
  if (rest.length === 0) return false;

  // Host: dot-separated labels ending with a 2+ letter TLD, plus optional
  // port, path, query string, and fragment.
  const pattern =
    /^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}(:\d{1,5})?(\/[^\s]*)?$/;
  return pattern.test(rest);
}
