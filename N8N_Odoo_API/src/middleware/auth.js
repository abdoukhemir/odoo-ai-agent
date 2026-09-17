const authMiddleware = (req, res, next) => {
  const authHeader = req.headers.authorization;
  const apiKey = process.env.API_KEY;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Unauthorized: Missing or invalid Authorization header' });
  }

  const token = authHeader.substring(7); // Remove 'Bearer '

  if (token !== apiKey) {
    return res.status(401).json({ error: 'Unauthorized: Invalid API key' });
  }

  next();
};

module.exports = authMiddleware;