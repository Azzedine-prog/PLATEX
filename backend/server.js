import express from 'express';
import http from 'http';
import { Server as SocketIOServer } from 'socket.io';
import axios from 'axios';
import { Pool } from 'pg';

const app = express();
const server = http.createServer(app);
const io = new SocketIOServer(server, {
  cors: { origin: '*' }
});

app.use(express.json({ limit: '5mb' }));

const PORT = process.env.PORT || 3000;
const COMPILATION_URL = process.env.COMPILATION_URL || 'http://compilation-service:7000';
const DATABASE_URL = process.env.DATABASE_URL || 'postgresql://platex:platex@db:5432/platex';

const pool = new Pool({ connectionString: DATABASE_URL });

io.on('connection', (socket) => {
  socket.on('join', (room) => socket.join(room));
  socket.on('edit', ({ room, content }) => {
    socket.to(room).emit('edit', content);
  });
});

app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

app.post('/compile', async (req, res) => {
  const { files, main } = req.body || {};
  if (!files || !main || !files[main]) {
    return res.status(400).json({ message: 'Request must include main file and files map.' });
  }

  try {
    const response = await axios.post(`${COMPILATION_URL}/compile`, { files, main });
    res.json(response.data);
  } catch (err) {
    const status = err.response?.status || 500;
    const payload = err.response?.data || { message: err.message };
    res.status(status).json(payload);
  }
});

app.get('/documents', async (_req, res) => {
  try {
    const result = await pool.query('SELECT id, name, updated_at FROM documents ORDER BY updated_at DESC LIMIT 20');
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ message: 'Failed to query documents', detail: err.message });
  }
});

server.listen(PORT, () => {
  console.log(`Backend listening on port ${PORT}`);
});
