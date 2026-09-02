/**
 * Sliding Window In-Memory Rate Limiter Middleware
 * Inspired by SlowAPI / MUE-X Token Bucket
 */

export function createRateLimiter({
  windowMs = 60000,   // 1 minute window
  maxRequests = 60,   // Max requests per window
  message = "Çok fazla istek gönderildi. Lütfen biraz sonra tekrar deneyin."
} = {}) {
  const requestHistory = new Map(); // IP -> Array of timestamps

  // Cleanup expired timestamps periodically (every 5 minutes)
  setInterval(() => {
    const now = Date.now();
    for (const [ip, timestamps] of requestHistory.entries()) {
      const valid = timestamps.filter((t) => now - t < windowMs);
      if (valid.length === 0) {
        requestHistory.delete(ip);
      } else {
        requestHistory.set(ip, valid);
      }
    }
  }, 300000);

  return function rateLimiterMiddleware(req, res, next) {
    const clientIp = req.headers["x-forwarded-for"] || req.socket.remoteAddress || "127.0.0.1";
    const now = Date.now();

    const timestamps = requestHistory.get(clientIp) || [];
    // Filter timestamps within current window
    const recentTimestamps = timestamps.filter((t) => now - t < windowMs);

    if (recentTimestamps.length >= maxRequests) {
      const oldest = recentTimestamps[0];
      const retryAfterSeconds = Math.ceil((windowMs - (now - oldest)) / 1000);

      res.setHeader("Retry-After", retryAfterSeconds);
      return res.status(429).json({
        success: false,
        error: message,
        retryAfterSeconds
      });
    }

    recentTimestamps.push(now);
    requestHistory.set(clientIp, recentTimestamps);

    res.setHeader("X-RateLimit-Limit", maxRequests);
    res.setHeader("X-RateLimit-Remaining", Math.max(0, maxRequests - recentTimestamps.length));

    next();
  };
}
