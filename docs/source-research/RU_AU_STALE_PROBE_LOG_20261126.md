# RU/AU Expansion & Stale Source Recovery Probe Log

- Probe time (Asia/Shanghai): `2026-11-26T20:29:55.693386+08:00`
- Today window (Asia/Shanghai): `2026-11-26`
- Total probed: `18`

## Summary Table

| Group | source_id | Name | Type | Scope | HTTP | Entries | Today? | Today N | Latest (Shanghai) | Error |
|---|---|---|---|---|---:|---:|---|---:|---|---|
| RU_media | `ru_moscow_times` | The Moscow Times (RSS) | `mainstream_independent` | `GENERAL_NEWS` | 200 | 50 | YES | 7 | `2026-11-26T19:49:04+08:00` | — |
| RU_media | `ru_meduza` | Meduza (Russian RSS) | `mainstream_independent` | `GENERAL_NEWS` | 200 | 30 | YES | 26 | `2026-11-26T20:01:10+08:00` | — |
| RU_media | `ru_rt_russia` | RT — Russia News (RSS) | `state_controlled` | `GENERAL_NEWS` | 200 | 100 | YES | 5 | `2026-11-26T20:02:38+08:00` | — |
| AU_media | `au_smh_world` | Sydney Morning Herald — World (RSS) | `mainstream_independent` | `INTERNATIONAL_NEWS` | 200 | 20 | YES | 12 | `2026-11-26T15:25:42+08:00` | — |
| AU_media | `au_sbs_world` | SBS News — World (RSS) | `public_service` | `INTERNATIONAL_NEWS` | 200 | 25 | YES | 4 | `2026-11-26T16:21:28+08:00` | — |
| AU_media | `au_abc_justin` | ABC News Australia — Just In (RSS) | `public_service` | `GENERAL_NEWS` | 200 | 25 | YES | 12 | `2026-11-26T14:08:29+08:00` | — |
| STALE_VOA | `voa_try1_top_en` | VOA English Top Stories | `state_controlled` | `INTERNATIONAL_NEWS` | 200 | 20 | NO | 0 | `2025-03-15T10:05:55+08:00` | — |
| STALE_VOA | `voa_try2_china_alt` | VOA China Alt Feed | `state_controlled` | `CHINA_FOCUSED` | 200 | 0 | NO | 0 | `—` | — |
| STALE_VOA | `voa_try3_mandarin_top` | VOA Chinese (Mandarin) Top Stories | `state_controlled` | `CHINA_FOCUSED` | 200 | 0 | NO | 0 | `—` | — |
| STALE_VOA | `voa_try4_mandarin_china` | VOA Chinese — China Desk | `state_controlled` | `CHINA_FOCUSED` | 200 | 0 | NO | 0 | `—` | — |
| STALE_VOA | `voa_try5_world` | VOA English World | `state_controlled` | `INTERNATIONAL_NEWS` | 200 | 0 | NO | 0 | `—` | parse_error: <unknown>:2:0: syntax error |
| STALE_STATE | `state_try1_browser_ua` | State Dept Press Releases (Browser UA) | `gov_comms` | `GOVERNMENT_RELEASES` | 407 | 0 | NO | 0 | `—` | HTTP 407 |
| STALE_STATE | `state_try2_alt_path` | State Dept Press Releases Alt Path | `gov_comms` | `GOVERNMENT_RELEASES` | 407 | 0 | NO | 0 | `—` | HTTP 407 |
| STALE_STATE | `state_try3_main_feed` | State Dept Main Feed | `gov_comms` | `GOVERNMENT_RELEASES` | 407 | 0 | NO | 0 | `—` | HTTP 407 |
| STALE_STATE | `state_try4_gh_mirror` | State Dept Press Releases (GitHub RSS Mirror) | `gov_comms` | `GOVERNMENT_RELEASES` | 200 | 10 | NO | 0 | `2026-11-25T22:00:00+08:00` | — |
| STALE_IE | `ie_try1_world_browser` | Indian Express — World (Browser UA) | `mainstream_independent` | `INTERNATIONAL_NEWS` | 403 | 0 | NO | 0 | `—` | HTTP 403 |
| STALE_IE | `ie_try2_india_browser` | Indian Express — India (Browser UA) | `mainstream_independent` | `GENERAL_NEWS` | 403 | 0 | NO | 0 | `—` | HTTP 403 |
| STALE_IE | `ie_try3_main_browser` | Indian Express — Main (Browser UA) | `mainstream_independent` | `GENERAL_NEWS` | 403 | 0 | NO | 0 | `—` | HTTP 403 |

## Sample 2 Items per Source

### `ru_moscow_times` — The Moscow Times (RSS) (RU_media)
- Feed: `https://www.themoscowtimes.com/rss/news`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `50` | Today (2026-11-26): `YES` (7)
  1. **Judge Confiscates $11.8M in Property From Krasnodar First Deputy Governor** | pub_sh=`2026-11-26T19:49:04+08:00` | today=`True` | article_http=`HTTP 200` | https://www.themoscowtimes.com/2026/11/26/judge-confiscates-11-8m-in-property-from-krasnodar-first-deputy-governor-a812381
  2. **Russia and Ukraine Hold First Exchange of War Dead Since Rebooted Peace Talks** | pub_sh=`2026-11-26T18:18:18+08:00` | today=`True` | article_http=`HTTP 200` | https://www.themoscowtimes.com/2026/11/26/russia-and-ukraine-hold-first-exchange-of-war-dead-since-rebooted-peace-talks-a812378

### `ru_meduza` — Meduza (Russian RSS) (RU_media)
- Feed: `https://meduza.io/rss/all`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `30` | Today (2026-11-26): `YES` (26)
  1. **«Пожалуйста, верните нашей маленькой дочери ее дорогого папу». Жена японского журналиста Юки Имаи, обвиненного в России в шпионаже, попросила его освободить. Она от руки написала обращение на русском языке** | pub_sh=`2026-11-26T20:01:10+08:00` | today=`True` | article_http=`HTTP 200` | https://meduza.io/feature/2026/11/26/pozhaluysta-vernite-nashey-malenkoy-docheri-ee-dorogogo-papu
  2. **Латвийская airBaltic предложила пилотам выбрать между увольнением и переводом в Папуа — Новую Гвинею** | pub_sh=`2026-11-26T19:38:23+08:00` | today=`True` | article_http=`HTTP 200` | https://meduza.io/news/2026/11/26/latviyskaya-airbaltic-predlozhila-pilotam-vybrat-mezhdu-uvolneniem-i-perevodom-v-papua-novuyu-gvineyu

### `ru_rt_russia` — RT — Russia News (RSS) (RU_media)
- Feed: `https://www.rt.com/rss/russia/`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `100` | Today (2026-11-26): `YES` (5)
  1. **Crucified, stripped, and caged: Ukrainian soldiers tortured by their own commander (VIDEO)** | pub_sh=`2026-11-26T20:02:38+08:00` | today=`True` | article_http=`HTTP 200` | https://rt-english.com/russia/649376-ukraine-officer-torture-corruption-trial/?utm_source=rss&utm_medium=rss&utm_campaign=RSS
  2. **Kiev hits out at YouTube over Russian-language censorship refusal** | pub_sh=`2026-11-26T18:50:26+08:00` | today=`True` | article_http=`HTTP 200` | https://rt-english.com/russia/649381-russian-language-youtube-filter/?utm_source=rss&utm_medium=rss&utm_campaign=RSS

### `au_smh_world` — Sydney Morning Herald — World (RSS) (AU_media)
- Feed: `https://www.smh.com.au/rss/world.xml`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `20` | Today (2026-11-26): `YES` (12)
  1. **Multiple people killed in Egypt petrol fire** | pub_sh=`2026-11-26T15:25:42+08:00` | today=`True` | article_http=`HTTP 200` | https://www.smh.com.au/world/multiple-people-killed-in-egypt-petrol-fire-20261126-p61hdz.html?ref=rss&utm_medium=rss&utm_source=rss_world
  2. **Vance has aligned himself with the tech bros. Has he miscalculated?** | pub_sh=`2026-11-26T12:30:00+08:00` | today=`True` | article_http=`HTTP 200` | https://www.smh.com.au/world/north-america/vance-has-aligned-himself-with-the-tech-bros-has-he-miscalculated-20261126-p61hjc.html?ref=rss&utm_medium=rss&utm_source=rss_world

### `au_sbs_world` — SBS News — World (RSS) (AU_media)
- Feed: `https://www.sbs.com.au/news/topic/world/feed`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `25` | Today (2026-11-26): `YES` (4)
  1. **16 dead and 10 missing as rescuers battle flooded Indonesian gold mine** | pub_sh=`2026-11-26T16:21:28+08:00` | today=`True` | article_http=`HTTP 200` | https://www.sbs.com.au/news/article/flooded-indonesian-gold-mine-rescuers/ajvtzsxod
  2. **A year after Hong Kong's deadliest fire in decades, authorities are wary of memorials** | pub_sh=`2026-11-26T15:00:35+08:00` | today=`True` | article_http=`HTTP 200` | https://www.sbs.com.au/news/article/hong-kong-fire-anniversary-memorial-protests/qf6dh1y3q

### `au_abc_justin` — ABC News Australia — Just In (RSS) (AU_media)
- Feed: `https://www.abc.net.au/news/feed/2942460/rss.xml`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `25` | Today (2026-11-26): `YES` (12)
  1. **Returning Matildas star Cooney-Cross wants to make late mum 'proud'** | pub_sh=`2026-11-26T14:08:29+08:00` | today=`True` | article_http=`HTTP 200` | https://www.abc.net.au/news/2026-11-26/matildas-star-kyra-cooney-cross-making-mum-proud/107431272
  2. **NRL scraps All Stars game for 2027 preseason** | pub_sh=`2026-11-26T10:55:14+08:00` | today=`True` | article_http=`HTTP 200` | https://www.abc.net.au/news/2026-11-26/nrl-scraps-all-stars-game-for-2027-preseason/107430180

### `voa_try1_top_en` — VOA English Top Stories (STALE_VOA)
- Feed: `https://www.voanews.com/api/z-$otevtiq`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `NO` (0)
  1. **US to expel South Africa ambassador as relations deteriorate** | pub_sh=`2025-03-15T10:05:55+08:00` | today=`False` | article_http=`HTTP 200` | https://www.voanews.com/a/us-to-expel-south-africa-ambassador-as-relations-deteriorate/8011493.html
  2. **Archaeologists use song to herald findings in Guinea-Bissau dig** | pub_sh=`2025-03-15T06:39:48+08:00` | today=`False` | article_http=`HTTP 200` | https://www.voanews.com/a/archaeologists-use-song-to-herald-findings-in-guinea-bissau-dig-/8011218.html

### `voa_try2_china_alt` — VOA China Alt Feed (STALE_VOA)
- Feed: `https://www.voanews.com/api/zmgqoe$moi`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `0` | Today (2026-11-26): `NO` (0)

### `voa_try3_mandarin_top` — VOA Chinese (Mandarin) Top Stories (STALE_VOA)
- Feed: `https://www.voachinese.com/api/z-$otevtiq`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `0` | Today (2026-11-26): `NO` (0)

### `voa_try4_mandarin_china` — VOA Chinese — China Desk (STALE_VOA)
- Feed: `https://www.voachinese.com/api/zmjuqtl-vomx-tpey_jqq`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `0` | Today (2026-11-26): `NO` (0)

### `voa_try5_world` — VOA English World (STALE_VOA)
- Feed: `https://www.voanews.com/api/z_-mqyl-vomx-tpey_jqq`
- HTTP: `200` | Content-Type: `text/plain` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `parse_error: <unknown>:2:0: syntax error`

### `state_try1_browser_ua` — State Dept Press Releases (Browser UA) (STALE_STATE)
- Feed: `https://www.state.gov/rss-feed/press-releases/feed/`
- HTTP: `407` | Content-Type: `` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 407`

### `state_try2_alt_path` — State Dept Press Releases Alt Path (STALE_STATE)
- Feed: `https://www.state.gov/press-releases/feed/`
- HTTP: `407` | Content-Type: `` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 407`

### `state_try3_main_feed` — State Dept Main Feed (STALE_STATE)
- Feed: `https://www.state.gov/feed/`
- HTTP: `407` | Content-Type: `` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 407`

### `state_try4_gh_mirror` — State Dept Press Releases (GitHub RSS Mirror) (STALE_STATE)
- Feed: `https://raw.githubusercontent.com/markschaver/State-Department-PR/master/data.rss`
- HTTP: `200` | Content-Type: `text/plain` | Entries: `10` | Today (2026-11-26): `NO` (0)
  1. **Suriname National Day** | pub_sh=`2026-11-25T22:00:00+08:00` | today=`False` | article_http=`HTTP 407` | https://www.state.gov/releases/office-of-the-spokesman/2026/11/suriname-national-day-2/
  2. **Venezuela’s Reconciliation Talks Continued Progress Toward an Enduring Democracy** | pub_sh=`2026-11-25T09:37:32+08:00` | today=`False` | article_http=`HTTP 407` | https://www.state.gov/releases/office-of-the-spokesman/2026/11/venezuelas-reconciliation-talks-continued-progress-toward-an-enduring-democracy/

### `ie_try1_world_browser` — Indian Express — World (Browser UA) (STALE_IE)
- Feed: `https://indianexpress.com/section/world/feed/`
- HTTP: `403` | Content-Type: `text/html` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 403`

### `ie_try2_india_browser` — Indian Express — India (Browser UA) (STALE_IE)
- Feed: `https://indianexpress.com/section/india/feed/`
- HTTP: `403` | Content-Type: `text/html` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 403`

### `ie_try3_main_browser` — Indian Express — Main (Browser UA) (STALE_IE)
- Feed: `https://indianexpress.com/feed/`
- HTTP: `403` | Content-Type: `text/html` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 403`

## GDELT DOC 2.0 API Probe (`timespan=24h`, `maxrecords=20`)

| source_id | Country | HTTP | Articles | Top Domains | Error |
|---|---|---:|---:|---|---|
| `ru_gdelt_china` | `RU` | 200 | 20 | 1prime.ru, amic.ru, amur.info, inosmi.ru, mk.ru | — |
| `au_gdelt_china` | `AU` | 429 | 0 | — | HTTP 429: Please limit requests to one every 5 seconds or contact kalev.leetaru5@gmail.com for larger queries. All high-traffic users should switch to |
