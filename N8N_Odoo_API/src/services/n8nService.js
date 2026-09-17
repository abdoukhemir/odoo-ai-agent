const axios = require('axios');

const sendToN8n = async (message) => {
  const webhookUrl = process.env.N8N_WEBHOOK_URL;

  if (!webhookUrl) {
    throw new Error('N8N_WEBHOOK_URL environment variable is not set');
  }

  const payload = {
    message: message,
    channel_id: 1,
    user_id: 1
  };

  console.log('Sending to n8n:', JSON.stringify(payload, null, 2));

  try {
    const response = await axios.post(webhookUrl, payload, {
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 0 // 30 seconds
    });

    console.log('N8n response:', JSON.stringify(response.data, null, 2));
    return response.data;
  } catch (error) {
    console.error('Error calling n8n:', error.message);
    throw error;
  }
};

module.exports = {
  sendToN8n
};