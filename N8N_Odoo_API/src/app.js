const express = require('express');
const chatRoutes = require('./routes/chat');

const app = express();

// Middleware
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Routes
app.use('/v1/chat/completions', chatRoutes);

module.exports = app;