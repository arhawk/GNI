# US Source Probe Log

- Probe time (Asia/Shanghai): `2026-11-26T12:09:01.615893+08:00`
- Today window (Asia/Shanghai): `2026-11-26`
- Total probed: `17`

## Summary Table

| Group | source_id | Name | Type | Scope | HTTP | Entries | Today? | Today N | Latest (Shanghai) | Error |
|---|---|---|---|---|---:|---:|---|---:|---|---|
| existing_active | `us_voa_english` | Voice of America — China News (RSS) | `state_controlled` | `CHINA_FOCUSED` | 200 | 20 | NO | 0 | `2025-03-15T08:53:12+08:00` | — |
| existing_active | `us_voa_east_asia` | Voice of America — East Asia News (RSS) | `state_controlled` | `CHINA_FOCUSED` | 200 | 20 | NO | 0 | `2025-03-15T08:53:12+08:00` | — |
| existing_active | `us_rfa_english` | Radio Free Asia (English RSS) | `state_controlled` | `CHINA_FOCUSED` | 200 | 30 | YES | 1 | `2026-11-26T01:13:29+08:00` | — |
| existing_active | `us_state_press` | U.S. Department of State — Press Releases (RSS) | `gov_comms` | `GOVERNMENT_RELEASES` | 407 | 0 | NO | 0 | `—` | HTTP 407 |
| existing_inactive | `us_rfa_mandarin` | Radio Free Asia (Mandarin RSS) | `state_controlled` | `CHINA_FOCUSED` | 200 | 30 | NO | 0 | `2026-11-25T16:29:39+08:00` | — |
| existing_inactive | `us_defense_news` | U.S. Department of Defense News | `gov_comms` | `GOVERNMENT_RELEASES` | 200 | 10 | YES | 3 | `2026-11-26T04:50:31+08:00` | — |
| existing_inactive | `us_federal_register_state` | Federal Register — State Department | `gov_comms` | `GOVERNMENT_RELEASES` | 200 | 26 | NO | 0 | `2026-11-24T13:00:00+08:00` | — |
| P1 | `us_npr_news` | NPR News | `public_service` | `GENERAL_NEWS` | 200 | 10 | YES | 2 | `2026-11-26T05:02:58+08:00` | — |
| P1 | `us_pbs_newshour` | PBS NewsHour Headlines | `public_service` | `GENERAL_NEWS` | 200 | 20 | YES | 20 | `2026-11-26T08:02:17+08:00` | — |
| P1 | `us_nbc_news` | NBC News — Top News | `mainstream_independent` | `GENERAL_NEWS` | 200 | 25 | YES | 12 | `2026-11-26T09:32:59+08:00` | — |
| P1 | `us_cbs_news` | CBS News — Latest | `mainstream_independent` | `GENERAL_NEWS` | 200 | 30 | YES | 29 | `2026-11-26T11:31:32+08:00` | — |
| P1 | `us_abc_news` | ABC News — Top Stories | `mainstream_independent` | `GENERAL_NEWS` | 200 | 25 | YES | 8 | `2026-11-26T10:17:57+08:00` | — |
| P2 | `us_nyt_world` | The New York Times — World | `mainstream_independent` | `INTERNATIONAL_NEWS` | 200 | 58 | YES | 17 | `2026-11-26T09:25:49+08:00` | — |
| P2 | `us_nyt_us` | The New York Times — US | `mainstream_independent` | `GENERAL_NEWS` | 200 | 30 | YES | 18 | `2026-11-26T11:42:51+08:00` | — |
| P2 | `us_fox_news` | Fox News — Latest | `mainstream_independent` | `GENERAL_NEWS` | 200 | 25 | YES | 25 | `2026-11-26T12:05:14+08:00` | — |
| P2 | `us_politico` | Politico — Politics | `mainstream_independent` | `TOPIC_FEED` | 200 | 30 | NO | 0 | `2026-11-25T18:45:00+08:00` | — |
| P2 | `us_the_hill` | The Hill — News | `mainstream_independent` | `TOPIC_FEED` | 200 | 15 | YES | 15 | `2026-11-26T11:40:32+08:00` | — |

## Sample 2 Items per Source

### `us_voa_english` — Voice of America — China News (RSS) (existing_active)
- Feed: `https://www.voanews.com/api/zmjuqtl-vomx-tpey_jqq`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `NO` (0)
  1. **Russian foreign minister exaggerates Russia-China relations, ignores nuances** | pub_sh=`2025-03-15T08:53:12+08:00` | today=`False` | article_http=`HTTP 200` | https://www.voanews.com/a/russian-foreign-minister-exaggerates-russia-china-relations-ignores-nuances/8011464.html
  2. **Chinese officials look to limit social media and screen time in China** | pub_sh=`2025-03-14T23:10:21+08:00` | today=`False` | article_http=`HTTP 200` | https://www.voanews.com/a/chinese-officials-look-to-limit-social-media-and-screen-time-in-china-/8010657.html

### `us_voa_east_asia` — Voice of America — East Asia News (RSS) (existing_active)
- Feed: `https://www.voanews.com/api/zobo_l-vomx-tpepvmv`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `NO` (0)
  1. **Russian foreign minister exaggerates Russia-China relations, ignores nuances** | pub_sh=`2025-03-15T08:53:12+08:00` | today=`False` | article_http=`HTTP 200` | https://www.voanews.com/a/russian-foreign-minister-exaggerates-russia-china-relations-ignores-nuances/8011464.html
  2. **Chinese officials look to limit social media and screen time in China** | pub_sh=`2025-03-14T23:10:21+08:00` | today=`False` | article_http=`HTTP 200` | https://www.voanews.com/a/chinese-officials-look-to-limit-social-media-and-screen-time-in-china-/8010657.html

### `us_rfa_english` — Radio Free Asia (English RSS) (existing_active)
- Feed: `https://www.rfa.org/english/rss`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `30` | Today (2026-11-26): `YES` (1)
  1. **China investigates Shanghai party chief, raising questions over Xi’s succession plans** | pub_sh=`2026-11-26T01:13:29+08:00` | today=`True` | article_http=`HTTP 200` | https://rfa.org/english/china/2026/11/25/chen-jining-china-investigation-/
  2. **China pushes sovereignty claims through patriotic cruises to disputed Paracel Islands** | pub_sh=`2026-11-25T16:07:22+08:00` | today=`False` | article_http=`HTTP 200` | https://rfa.org/english/vietnam/2026/11/25/vietnam-china-paracels-south-china-sea/

### `us_state_press` — U.S. Department of State — Press Releases (RSS) (existing_active)
- Feed: `https://www.state.gov/rss-feed/press-releases/feed/`
- HTTP: `407` | Content-Type: `` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 407`

### `us_rfa_mandarin` — Radio Free Asia (Mandarin RSS) (existing_inactive)
- Feed: `https://www.rfa.org/mandarin/rss`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `30` | Today (2026-11-26): `NO` (0)
  1. **陈吉宁遭调查 专家：21大人事添变数** | pub_sh=`2026-11-25T16:29:39+08:00` | today=`False` | article_http=`HTTP 200` | https://rfa.org/mandarin/yataibaodao/2026/11/25/chen-ji-ning-under-scrutiny/
  2. **文革六十周年：从历史记忆到现实警示** | pub_sh=`2026-11-25T06:03:54+08:00` | today=`False` | article_http=`HTTP 200` | https://rfa.org/mandarin/xinwenkuaixun/2026/11/24/cultural-revolution-60th-anniversary/

### `us_defense_news` — U.S. Department of Defense News (existing_inactive)
- Feed: `https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?max=10&ContentType=1&Site=945`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `10` | Today (2026-11-26): `YES` (3)
  1. **U.S., Mexican Army Leaders Strengthen Bilateral Partnership** | pub_sh=`2026-11-26T04:50:31+08:00` | today=`True` | article_http=`HTTP 403` | https://www.war.gov/News/News-Stories/Article/Article/4660227/us-mexican-army-leaders-strengthen-bilateral-partnership/
  2. **Hegseth Directs Military Pay System Modernization Prioritizing Warfighters** | pub_sh=`2026-11-26T02:35:00+08:00` | today=`True` | article_http=`HTTP 403` | https://www.war.gov/News/News-Stories/Article/Article/4660118/hegseth-directs-military-pay-system-modernization-prioritizing-warfighters/

### `us_federal_register_state` — Federal Register — State Department (existing_inactive)
- Feed: `https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=state-department`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `26` | Today (2026-11-26): `NO` (0)
  1. **Notice of Department of State Sanctions Actions** | pub_sh=`2026-11-24T13:00:00+08:00` | today=`False` | article_http=`HTTP 200` | https://www.federalregister.gov/documents/2026/11/24/2026-23902/notice-of-department-of-state-sanctions-actions
  2. **Notice of Department of State Sanctions Actions** | pub_sh=`2026-11-24T13:00:00+08:00` | today=`False` | article_http=`HTTP 200` | https://www.federalregister.gov/documents/2026/11/24/2026-23899/notice-of-department-of-state-sanctions-actions

### `us_npr_news` — NPR News (P1)
- Feed: `https://feeds.npr.org/1001/rss.xml`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `10` | Today (2026-11-26): `YES` (2)
  1. **At this Little Free Bakery in Austin, neighbors come for the pastries and stay for community connection** | pub_sh=`2026-11-26T05:02:58+08:00` | today=`True` | article_http=`timeout` | https://www.npr.org/2026/11/25/nx-s1-6005522/little-free-bakery-austin-community-connection
  2. **Group of Senate Democrats push to add freshman to leadership** | pub_sh=`2026-11-26T01:30:47+08:00` | today=`True` | article_http=`timeout` | https://www.npr.org/2026/11/25/g-s1-155518/senate-democrats-freshman-leadership-schumer-van-hollen

### `us_pbs_newshour` — PBS NewsHour Headlines (P1)
- Feed: `https://www.pbs.org/newshour/feeds/rss/headlines`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `20` | Today (2026-11-26): `YES` (20)
  1. **Small plane crash off Mississippi coast kills extended family of 6 on fishing trip** | pub_sh=`2026-11-26T08:02:17+08:00` | today=`True` | article_http=`HTTP 200` | https://www.pbs.org/newshour/nation/small-plane-crash-off-mississippi-coast-kills-extended-family-of-6-on-fishing-trip
  2. **WATCH: Vance defends Iowa lead azide detonation as he visits Air Force troops in Ohio** | pub_sh=`2026-11-26T07:51:49+08:00` | today=`True` | article_http=`HTTP 200` | https://www.pbs.org/newshour/politics/watch-vance-defends-iowa-lead-azide-detonation-as-he-visits-air-force-troops-in-ohio

### `us_nbc_news` — NBC News — Top News (P1)
- Feed: `https://feeds.nbcnews.com/nbcnews/public/news`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `25` | Today (2026-11-26): `YES` (12)
  1. **Questions linger about lead pollution from Iowa blast, despite officials’ assurances** | pub_sh=`2026-11-26T09:32:59+08:00` | today=`True` | article_http=`HTTP 200` | https://www.nbcnews.com/science/environment/questions-lead-dust-pollution-safe-iowa-detonation-tests-rcna611366
  2. **Thanksgiving Day parade celebrates 100 years** | pub_sh=`2026-11-26T08:57:47+08:00` | today=`True` | article_http=`HTTP 200` | https://www.nbcnews.com/nightly-news/video/thanksgiving-day-parade-celebrates-100-years-274202181863

### `us_cbs_news` — CBS News — Latest (P1)
- Feed: `https://www.cbsnews.com/latest/rss/main`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `30` | Today (2026-11-26): `YES` (29)
  1. **Trump owned millions in Nvidia stock as he pressed for Jensen Huang's reinstatement** | pub_sh=`2026-11-26T11:31:32+08:00` | today=`True` | article_http=`HTTP 200` | https://www.cbsnews.com/news/trump-nvidia-stock-jensen-huang/
  2. **Army detonates toxic explosives at Iowa plant despite concerns** | pub_sh=`2026-11-26T11:30:47+08:00` | today=`True` | article_http=`HTTP 200` | https://www.cbsnews.com/news/iowa-army-ammunition-plant-unstable-explosives-detonation/

### `us_abc_news` — ABC News — Top Stories (P1)
- Feed: `https://abcnews.com/abcnews/topstories`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `25` | Today (2026-11-26): `YES` (8)
  1. **Federal officials say 'zero' airborne lead detected after Iowa munitions blast** | pub_sh=`2026-11-26T10:17:57+08:00` | today=`True` | article_http=`HTTP 200` | https://abcnews.com/US/iowa-detonation-lead-azide-army/story?id=138425051
  2. **Macy's Thanksgiving Day parade postponed due to weather** | pub_sh=`2026-11-26T10:16:54+08:00` | today=`True` | article_http=`HTTP 200` | https://abcnews.com/US/macys-thanksgiving-day-parade-postponed-sources/story?id=138452401

### `us_nyt_world` — The New York Times — World (P2)
- Feed: `https://rss.nytimes.com/services/xml/rss/nyt/World.xml`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `58` | Today (2026-11-26): `YES` (17)
  1. **How to Celebrate Thanksgiving as an Expat** | pub_sh=`2026-11-26T09:25:49+08:00` | today=`True` | article_http=`HTTP 403` | https://www.nytimes.com/2026/11/25/world/asia/friendsgiving-thanksgiving-expats.html
  2. **Africa C.D.C. Chief Faces Turmoil Over Management Amid Ebola Crisis** | pub_sh=`2026-11-26T08:11:25+08:00` | today=`True` | article_http=`HTTP 403` | https://www.nytimes.com/2026/11/25/world/africa/acdc-kaseya-staff-ebola.html

### `us_nyt_us` — The New York Times — US (P2)
- Feed: `https://rss.nytimes.com/services/xml/rss/nyt/US.xml`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `30` | Today (2026-11-26): `YES` (18)
  1. **Border Barrier Cannot be Removed for Decades, Texas Republicans and D.O.J. Agree** | pub_sh=`2026-11-26T11:42:51+08:00` | today=`True` | article_http=`HTTP 403` | https://www.nytimes.com/2026/11/25/us/politics/texas-border-legal-settlement-trump.html
  2. **Trump Rejoiced in the Market’s Nvidia Surge. It Didn’t Last Long.** | pub_sh=`2026-11-26T09:53:20+08:00` | today=`True` | article_http=`HTTP 403` | https://www.nytimes.com/2026/11/25/us/politics/trump-nvidia-stock-market.html

### `us_fox_news` — Fox News — Latest (P2)
- Feed: `https://moxie.foxnews.com/google-publisher/latest.xml`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `25` | Today (2026-11-26): `YES` (25)
  1. **Federal judge blocks FCC from reviewing ABC station licenses early as part of agency's spat with network** | pub_sh=`2026-11-26T12:05:14+08:00` | today=`True` | article_http=`HTTP 200` | https://www.foxnews.com/media/federal-judge-blocks-fcc-reviewing-abc-station-licenses-early-agency-spat-network
  2. **Fanatics Sportsbook Celebrates $1 Billion in FanCash With $200 in Bonus Bets and an NBA Jersey for New Custome** | pub_sh=`2026-11-26T11:57:27+08:00` | today=`True` | article_http=`HTTP 200` | https://www.foxnews.com/outkick-betting/fanatics-sportsbook-celebrates-1-billion-fancash-200-bonus-bets-nba-jersey-new-custome

### `us_politico` — Politico — Politics (P2)
- Feed: `https://rss.politico.com/politics-news.xml`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `30` | Today (2026-11-26): `NO` (0)
  1. **Moderates want a Medicare for All rebrand** | pub_sh=`2026-11-25T18:45:00+08:00` | today=`False` | article_http=`HTTP 200` | https://www.politico.com/video/2026/11/25/moderates-want-a-medicare-for-all-rebrand-2237528
  2. **Republicans’ midterm reckoning comes for the RNC** | pub_sh=`2026-11-25T18:45:00+08:00` | today=`False` | article_http=`HTTP 200` | https://www.politico.com/news/2026/11/25/rnc-gruters-crosbie-republican-party-future-01182563

### `us_the_hill` — The Hill — News (P2)
- Feed: `https://thehill.com/news/feed/`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `15` | Today (2026-11-26): `YES` (15)
  1. **Hochul declares state of emergency in New York counties ahead of Thanksgiving storm** | pub_sh=`2026-11-26T11:40:32+08:00` | today=`True` | article_http=`HTTP 200` | https://thehill.com/homenews/state-watch/6244382-hochul-declares-thanksgiving-emergency/
  2. **Judge sides against Democrats on taxpayer-funded pro-Trump ads** | pub_sh=`2026-11-26T11:09:54+08:00` | today=`True` | article_http=`HTTP 200` | https://thehill.com/regulation/court-battles/6244361-judge-denies-dnc-ad-challenge/
