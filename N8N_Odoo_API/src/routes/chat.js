const express = require('express');
const chatController = require('../controllers/chatController');
const authMiddleware = require('../middleware/auth');

const router = express.Router();

// POST /v1/chat/completions
router.post('/', authMiddleware, chatController.handleChatCompletion);

module.exports = router;