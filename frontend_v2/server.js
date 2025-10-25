const express = require('express');
const path = require('path');

const app = express();
const PORT = 3001;

// Serve static files from the current directory
app.use(express.static('.'));

// Start the server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running at http://localhost:${PORT}/`);
});