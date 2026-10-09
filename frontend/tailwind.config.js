export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  safelist: ['status-normal', 'status-attention', 'status-critical', 'delta-improved', 'delta-risk', 'metric-overdue', 'metric-total'],
  theme: { extend: { fontFamily: { sans: ['Geist', 'Segoe UI', 'sans-serif'] } } },
  plugins: [],
};
