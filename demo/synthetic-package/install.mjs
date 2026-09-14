const allowed = new URL(process.env.SSS_DEMO_CANARY_URL ?? 'http://canary:8090/v1/events');
if (allowed.hostname !== 'canary' || allowed.pathname !== '/v1/events') {
  throw new Error('controlled demo package refuses an unexpected destination');
}
const response = await fetch(allowed, {
  method: 'POST',
  headers: {
    authorization: `Bearer ${process.env.SSS_CANARY_TOKEN ?? ''}`,
    'content-type': 'application/json',
  },
  body: JSON.stringify({ marker: 'DEMO_ONLY_NOT_A_SECRET' }),
});
if (!response.ok) throw new Error(`controlled canary rejected event: ${response.status}`);
