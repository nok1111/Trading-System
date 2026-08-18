const WebSocket = require('ws');
const ws = new WebSocket('ws://localhost:1420/api/ws/prices?token=test');
ws.on('open', () => { console.log('CONNECTED OK'); ws.close(); process.exit(0); });
ws.on('error', (e) => { console.log('FAILED:', e.message); process.exit(1); });
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 5000);
