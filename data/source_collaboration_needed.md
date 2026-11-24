# 源接通协作清单（needs_you）

生成时间（UTC）：2026-11-24T11:30:55.307021+00:00

本表列出**无法单方接通**、需要你申请账号/白名单/备用 URL 的源。密钥只放本机 `.env`，不要贴到聊天。

## 需要你协作

| 源 | 国 | 卡点 | 你去哪 | 提供什么 | 备注 |
|----|----|------|--------|----------|------|
| USAGM Direct API | US | 503 / 需 Affiliate 加盟 | https://direct.usagm.gov/ | 在 Direct 门户注册 Affiliate；把 API/工作流凭证写入本机 .env（勿贴聊天） | 下一阶段 ApiAdapter |
| TASS B2B API | RU | 商业门户非公开 RSS | https://b2b.tass.ru/news-services | 商务订阅；提供 API/FTP 账号到 .env | 下一阶段 ApiAdapter |
| 印度 MEA | IN | 持续 HTTP 403 | https://www.mea.gov.in/ | 机构 IP 白名单 / 官方数据合作；或书面确认可用 PIB MinId=4 HTML（需我们做 web_adapter） | web_adapter 或白名单 |
| 澳外长 / DFAT Ministers / Defence | AU | 本网段超时 / 断连 | https://www.foreignminister.gov.au/rss.xml | 是否需澳区出口 IP/VPN；或提供官方备用 feed URL | 网络/备用 URL |
| 德国外交部 Auswärtiges Amt | DE | 本网段 HTTP 400（含官方 static RSS） | https://www.auswaertiges-amt.de/de/newsroom/presse/newsletter/rss | 官方 RSS 目录可访问链接，或新闻稿订阅账号，或德区出口 | 出口 IP / 订阅 |
| 德国联邦政府新闻 | DE | HTTP 400 | https://www.bundesregierung.de/ | 同外交部 | 出口 IP / 订阅 |
| 俄罗斯外交部 MID | RU | rss.php 返回 HTML 假饲料 | https://mid.ru/en/rss.php | 提供当前可用的真 RSS/Atom URL；或允许 HTML 列表抓取 | 真 URL 或 web_adapter |
| 俄罗斯国防部 MoD | RU | SSL UNEXPECTED_EOF | https://function.mil.ru/ | 备用 HTTPS URL / TLS 指引 / 可达出口 | TLS/URL |
| White House / USA.gov | US | 无可用外交叙事 RSS（/news/feed 偏立法） | https://www.whitehouse.gov/ | 确认是否有 briefing-room 公开 RSS；否则排期 WebAdapter | 下一阶段 web_adapter |
| data.gov.in / data.gov.au | IN/AU | 非叙事 Open Data | https://data.gov.in/ / https://data.gov.au/ | 无需申请——产品明确不接（统计 ≠ 官媒文章） | 不接 |

## 本轮已接通（新 ✓）

| source_id | 说明 |
|-----------|------|
| us_state_press | State.gov press-releases RSS；Mozilla-compatible UA；ingest 10 |
| us_voa_east_asia | VOA East Asia API RSS；ingest 20 |
| ru_sputnik_world | Sputnik Globe 恢复 active；ingest OK |

## 故意不接（产品口径，非“没修好”）

- 国内 denylist：NITI、PIB Hindi、TASS RU 全站、RIA 全站、DoD 运营稿、ABC Top、典礼稿等

- OpenData 统计 API：data.gov.in / data.gov.au

- Federal Register 不作主桌；RT Russia&FSU 不与 RT World 重复占槽

- 完整 ApiAdapter / WebAdapter：下一阶段开发（PIB MEA HTML、Newsonair WP JSON、WH HTML）
