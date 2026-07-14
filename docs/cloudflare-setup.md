# Cloudflare Setup for AI Code Mentor

Adding Cloudflare in front of your deployment gives you CDN caching, DDoS protection, HTTP/3, and global latency reduction at no cost.

## Prerequisites

- A domain (e.g., `yourdomain.com`) managed through a registrar that allows custom nameservers
- Your app deployed on Railway (or other platform)

## Setup Steps

### 1. Create a Cloudflare Account

Sign up at https://dash.cloudflare.com/sign-up

### 2. Add Your Domain

- In Cloudflare Dashboard → **Add a Site**
- Enter your domain (e.g., `aicodementor.com`)
- Select the **Free** plan

### 3. Update Nameservers

Cloudflare will show two nameserver addresses (e.g., `alice.ns.cloudflare.com`).
- Go to your domain registrar's DNS settings
- Replace your current nameservers with Cloudflare's
- Changes propagate in 5–30 minutes

### 4. Configure DNS Records

Once Cloudflare is active, add these DNS records in Cloudflare:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| CNAME | `@` | `your-railway-app.up.railway.app` | Proxied (orange cloud) |

If using Railway with a custom domain, Railway will provide the CNAME target.

### 5. Enable Performance Features

- **Auto Minify**: Dashboard → Speed → Optimization → Auto Minify (enable JS/CSS/HTML)
- **Brotli Compression**: Enabled by default on proxied traffic
- **HTTP/3**: Dashboard → Speed → Optimization → HTTP/3 (enable)
- **Caching Level**: Set to "Standard" in Caching → Configuration
- **Edge Cache TTL**: Respect existing headers (your Vite build already sets good cache headers)

### 6. Security Configuration

- **SSL/TLS → Overview**: Set to "Full (strict)" for end-to-end encryption
- **SSL/TLS → Edge Certificates**: Enable "Always Use HTTPS"
- **Security → WAF**: Start with "Essentially Off" and tune later if needed
- **Security → Settings**: Enable "Browser Integrity Check" and "Bot Fight Mode"

### 7. Optimize for Your Stack

Since AI Code Mentor has a Vite SPA frontend plus Flask API:

**Page Rules** (Free plan: 3 rules):
- `yourdomain.com/assets/*` → Cache Level: **Cache Everything**, Edge Cache TTL: **1 month**
- `yourdomain.com/` → Cache Level: **Standard**
- `yourdomain.com/api/v1/*` → Cache Level: **Bypass** (API responses are dynamic)

### 8. Verify Deployment

```bash
# Check HTTP/3 support
curl -I --http3 https://yourdomain.com

# Check Cloudflare headers
curl -I https://yourdomain.com | grep "cf-"

# Verify SSL
curl -vI https://yourdomain.com 2>&1 | grep "SSL connection"
```

## Expected Benefits

| Metric | Before | After (estimate) |
|--------|--------|-------------------|
| TTFB (global) | 200-800ms | 50-200ms |
| HTML cache hit ratio | 0% | 60-80% |
| Static asset load time | 100-500ms | 10-50ms |
| DDoS protection | None | Always-on |
| HTTP/3 support | No | Yes |

## Cost

**Free tier**: Unlimited traffic, DDoS protection, 3 Page Rules, 5 WAF rules

## Troubleshooting

- **Changes not propagating**: Wait 5-30 min for DNS. Use `dig` or `nslookup` to verify.
- **API calls failing**: Ensure API routes are **not cached** (Page Rule bypass). Check CORS config still allows your domain.
- **WebSocket (future)**: Cloudflare Free plan supports 1,000 WebSocket connections per minute.
- **Rate limiting**: Cloudflare Rate Limiting is available on Pro plan+. Use your app's existing Flask-Limiter for now.
