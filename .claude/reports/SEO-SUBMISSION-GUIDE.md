# Hướng dẫn Submit SEO — Wiii AI
**URL:** https://wiii.holilihu.online/
**Date:** 2026-03-14

---

## 1. Google Search Console (BẮT BUỘC)

### Bước 1: Truy cập
Vào https://search.google.com/search-console/welcome

### Bước 2: Thêm property
- Chọn **"URL prefix"**
- Nhập: `https://wiii.holilihu.online/`

### Bước 3: Xác minh ownership (chọn 1 trong các cách)
- **Cách 1 (Cloudflare DNS)**: Thêm TXT record vào DNS
- **Cách 2 (HTML tag)**: Thêm `<meta name="google-site-verification" content="..." />` vào index.html
- **Cách 3 (HTML file)**: Upload file `google*.html` vào /public/

### Bước 4: Submit Sitemap
- Vào **Sitemaps** → nhập `sitemap.xml` → Submit
- URL: https://wiii.holilihu.online/sitemap.xml

### Bước 5: Request Indexing
- Vào **URL Inspection** → nhập `https://wiii.holilihu.online/`
- Click **"Request Indexing"**

---

## 2. Bing Webmaster Tools

Vào https://www.bing.com/webmasters/
- Thêm site: `https://wiii.holilihu.online/`
- Submit sitemap: `https://wiii.holilihu.online/sitemap.xml`

---

## 3. Test Tools

| Tool | URL | Mục đích |
|------|-----|----------|
| Google Rich Results | https://search.google.com/test/rich-results?url=https%3A%2F%2Fwiii.holilihu.online%2F | Test JSON-LD structured data |
| Facebook Sharing Debugger | https://developers.facebook.com/tools/debug/?q=https%3A%2F%2Fwiii.holilihu.online%2F | Test OG image/tags |
| Twitter Card Validator | https://cards-dev.twitter.com/validator | Test Twitter card |
| PageSpeed Insights | https://pagespeed.web.dev/analysis?url=https%3A%2F%2Fwiii.holilihu.online%2F | Performance + SEO audit |

---

## 4. SEO Checklist (đã hoàn thành)

| Item | Status | File |
|------|--------|------|
| `<title>` tag | ✅ "Wiii — Trợ lý AI thông minh cho học tập và nghiên cứu" | index.html |
| `<meta description>` | ✅ 160 chars Vietnamese | index.html |
| `<meta keywords>` | ✅ Wiii, AI, hàng hải, COLREGs... | index.html |
| `<link canonical>` | ✅ https://wiii.holilihu.online/ | index.html |
| `<meta robots>` | ✅ index, follow | index.html |
| OG tags (7) | ✅ title, description, image, url, type, locale, site_name | index.html |
| Twitter Card | ✅ summary_large_image | index.html |
| JSON-LD | ✅ WebApplication schema | index.html |
| favicon.ico | ✅ Mascot 58KB (multi-size) | public/ |
| apple-touch-icon | ✅ 180px mascot | public/ |
| icon-192.png | ✅ Android | public/ |
| icon-512.png | ✅ PWA | public/ |
| og-image.png | ✅ 1200x630 social card | public/ |
| manifest.webmanifest | ✅ PWA metadata | public/ |
| robots.txt | ✅ Allow /, Disallow /api/ | public/ |
| sitemap.xml | ✅ Homepage entry | public/ |
| theme-color | ✅ #F97316 (orange) | index.html |
| lang="vi" | ✅ Vietnamese | index.html |
| Nginx cache headers | ✅ favicon 1h, robots 1d, index no-cache | nginx.conf |

---

## 5. Về SSR

**Wiii KHÔNG cần SSR** vì:
- Tất cả SEO meta tags đã có trong **static HTML** (index.html) — Google đọc được không cần JS
- Chat content ở **sau login** — không cần và không nên index
- JSON-LD structured data ở trong `<script>` tag — Google parse được mà không render JS
- OG image là static PNG — social platforms đọc được

**Khi nào cần SSR:**
- Nếu có blog/documentation public (chưa có)
- Nếu có landing page với nội dung SEO-heavy (chưa có)

---

## 6. Timeline ước tính

| Milestone | Thời gian |
|-----------|-----------|
| Google crawl sitemap | 1-3 ngày |
| Xuất hiện trong search results | 1-2 tuần |
| Favicon hiện trong search results | 2-4 tuần |
| Rich results (JSON-LD) | 2-4 tuần |
| OG image khi share link | Ngay lập tức (sau Facebook debug) |
