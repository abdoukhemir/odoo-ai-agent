const n8nService = require('../services/n8nService');

const handleChatCompletion = async (req, res) => {
  try {
    console.log('Received chat completion request:', JSON.stringify(req.body, null, 2));

    // Validate request
    if (!req.body.messages || !Array.isArray(req.body.messages) || req.body.messages.length === 0) {
      return res.status(400).json({ error: 'Invalid request: messages array is required' });
    }

    // Extract last user message
    const lastMessage = req.body.messages[req.body.messages.length - 1];
    if (lastMessage.role !== 'user') {
      return res.status(400).json({ error: 'Invalid request: last message must be from user' });
    }

    const userMessage = lastMessage.content;
    console.log('Extracted user message:', userMessage);

    // Call n8n service
    const n8nResponse = await n8nService.sendToN8n(userMessage);
    const reply = n8nResponse.reply || 'Sorry, no response generated.';
    console.log('N8n reply:', reply);

    // Generate response
    const response = {
      id: `chatcmpl-${crypto.randomUUID()}`,
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: 'n8n-odoo-agent',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: reply
          },
          finish_reason: 'stop'
        }
      ]
    };

    console.log('Sending response:', JSON.stringify(response, null, 2));
    res.json(response);

  } catch (error) {
    console.error('Error in chat completion:', error);
    if (error.response) {
      // n8n error
      res.status(500).json({ error: 'Internal server error: Failed to communicate with n8n' });
    } else {
      res.status(500).json({ error: 'Internal server error' });
    }
  }
};

module.exports = {
  handleChatCompletion
};