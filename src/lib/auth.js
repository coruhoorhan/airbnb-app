import jwt from 'jsonwebtoken';
import crypto from 'crypto';

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-key-do-not-use-in-prod";
const CSRF_SECRET = process.env.CSRF_SECRET || "dev-csrf-secret-key-do-not-use-in-prod";

if (process.env.NODE_ENV === "production") {
  if (JWT_SECRET === "dev-secret-key-do-not-use-in-prod") throw new Error("JWT_SECRET must be set in production");
  if (CSRF_SECRET === "dev-csrf-secret-key-do-not-use-in-prod") throw new Error("CSRF_SECRET must be set in production");
}

export function generateToken(user) {
  return jwt.sign(
    { id: user.id, email: user.email, isHost: user.isHost },
    JWT_SECRET,
    { expiresIn: '24h' }
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
  const cookieCsrfToken = req.cookies.csrfToken;

  if (!csrfToken || !cookieCsrfToken || csrfToken !== cookieCsrfToken) {
    return res.status(403).json({ success: false, error: 'Forbidden: Invalid CSRF token' });
  }

  next();
}
