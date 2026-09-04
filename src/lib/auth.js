import jwt from 'jsonwebtoken';
import crypto from 'crypto';

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-key-do-not-use-in-prod-which-is-at-least-thirty-two-chars";
const CSRF_SECRET = process.env.CSRF_SECRET || "dev-csrf-secret-key-do-not-use-in-prod-which-is-at-least-thirty-two-chars";

if (JWT_SECRET.length < 32) {
  throw new Error("JWT_SECRET must be at least 32 characters long.");
}

if (process.env.NODE_ENV === "production") {
  if (JWT_SECRET === "dev-secret-key-do-not-use-in-prod-which-is-at-least-thirty-two-chars") throw new Error("JWT_SECRET must be set in production");
  if (CSRF_SECRET === "dev-csrf-secret-key-do-not-use-in-prod-which-is-at-least-thirty-two-chars") throw new Error("CSRF_SECRET must be set in production");
}

export function generateToken(user) {
  return jwt.sign(
    { id: user.id, email: user.email, isHost: user.isHost },
    JWT_SECRET,
    { expiresIn: '1h' }
  );
}

export function verifyToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch (error) {
    return null;
  }
}

export function generateCsrfToken() {
  return crypto.randomBytes(32).toString('hex');
}

export function authMiddleware(req, res, next) {
  const token = req.cookies.token || req.headers.authorization?.split(' ')[1];

  if (!token) {
    return res.status(401).json({ success: false, error: 'Unauthorized: No token provided' });
  }

  const decoded = verifyToken(token);
  if (!decoded) {
    return res.status(401).json({ success: false, error: 'Unauthorized: Invalid token' });
  }

  req.user = decoded;
  next();
}

export function csrfMiddleware(req, res, next) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
    return next();
  }

  const csrfToken = req.headers['x-csrf-token'] || req.body._csrf;
  const cookieCsrfToken = req.cookies._csrf_secret;

  if (!csrfToken || !cookieCsrfToken || csrfToken !== cookieCsrfToken) {
    return res.status(403).json({ success: false, error: 'Forbidden: Invalid CSRF token' });
  }

  // Token rotation after successful state-changing request
  const newToken = generateCsrfToken();
  res.cookie("_csrf_secret", newToken, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  res.setHeader("x-csrf-token", newToken);

  next();
}
