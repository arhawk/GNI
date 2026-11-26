# Catalog US / IN / AU Source Probe Log

- Probe time (Asia/Shanghai): `2026-11-26T12:24:44.004135+08:00`
- Today window (Asia/Shanghai): `2026-11-26`
- Total probed: `12`

## Summary Table

| Group | source_id | Name | Type | Scope | HTTP | Entries | Today? | Today N | Latest (Shanghai) | Error |
|---|---|---|---|---|---:|---:|---|---:|---|---|
| US_gov | `us_whitehouse_briefings` | White House — Briefings & Statements | `gov_comms` | `GOVERNMENT_RELEASES` | 200 | 30 | NO | 0 | `2026-11-25T20:01:00+08:00` | — |
| US_gov | `us_whitehouse_actions` | White House — Presidential Actions | `gov_comms` | `GOVERNMENT_RELEASES` | 200 | 30 | NO | 0 | `2026-11-25T22:30:00+08:00` | — |
| US_media | `us_axios` | Axios | `mainstream_independent` | `GENERAL_NEWS` | 200 | 100 | YES | 6 | `2026-11-26T05:28:25+08:00` | — |
| US_media | `us_wsj` | Wall Street Journal — US News | `mainstream_independent` | `GENERAL_NEWS` | 200 | 40 | YES | 9 | `2026-11-26T07:38:00+08:00` | — |
| US_tech | `us_the_verge` | The Verge | `mainstream_independent` | `TOPIC_FEED` | 200 | 10 | YES | 10 | `2026-11-26T08:04:34+08:00` | — |
| US_tech | `us_mit_tech_review` | MIT Technology Review | `mainstream_independent` | `TOPIC_FEED` | 200 | 10 | YES | 1 | `2026-11-26T01:00:00+08:00` | — |
| US_tech | `us_wired` | Wired | `mainstream_independent` | `TOPIC_FEED` | 200 | 50 | YES | 1 | `2026-11-26T02:38:12+08:00` | — |
| IN_media | `in_the_hindu` | The Hindu — National | `mainstream_independent` | `GENERAL_NEWS` | 200 | 60 | YES | 60 | `2026-11-26T12:18:05+08:00` | — |
| IN_media | `in_indian_express` | The Indian Express — India | `mainstream_independent` | `GENERAL_NEWS` | 403 | 0 | NO | 0 | `—` | HTTP 403 |
| IN_media | `in_ndtv` | NDTV — Top Stories | `mainstream_independent` | `GENERAL_NEWS` | 200 | 20 | YES | 20 | `2026-11-26T12:13:56+08:00` | — |
| AU_media | `au_guardian` | The Guardian — Australia News | `mainstream_independent` | `GENERAL_NEWS` | 200 | 20 | YES | 8 | `2026-11-26T12:09:57+08:00` | — |
| AU_media | `au_guardian_pacific` | The Guardian — Pacific Islands | `mainstream_independent` | `INTERNATIONAL_NEWS` | 200 | 20 | NO | 0 | `2026-11-25T07:47:38+08:00` | — |

## Sample 2 Items per Source

### `us_whitehouse_briefings` — White House — Briefings & Statements (US_gov)
- Feed: `https://www.whitehouse.gov/briefings-statements/feed/`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `30` | Today (2026-11-26): `NO` (0)
  1. **First Lady Melania Trump Secures Reunification of Nine Additional Children with their Families** | pub_sh=`2026-11-25T20:01:00+08:00` | today=`False` | article_http=`HTTP 200` | https://www.whitehouse.gov/briefings-statements/2026/11/first-lady-melania-trump-secures-reunification-of-nine-additional-children-with-their-families/
  2. **Congressional Bills H.R. 1550, H.R. 4930, and H.R. 8552 Signed into Law** | pub_sh=`2026-11-24T07:39:52+08:00` | today=`False` | article_http=`HTTP 200` | https://www.whitehouse.gov/briefings-statements/2026/11/congressional-bills-h-r-1550-h-r-4930-and-h-r-8552-signed-into-law/

### `us_whitehouse_actions` — White House — Presidential Actions (US_gov)
- Feed: `https://www.whitehouse.gov/presidential-actions/feed/`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `30` | Today (2026-11-26): `NO` (0)
  1. **Thanksgiving Day, 2026** | pub_sh=`2026-11-25T22:30:00+08:00` | today=`False` | article_http=`HTTP 200` | https://www.whitehouse.gov/presidential-actions/2026/11/thanksgiving-day-2026/
  2. **Expeditious Enforcement of Capital Sentences and the Pursuit of Justice for Victims of Heinous Crimes** | pub_sh=`2026-11-24T07:36:12+08:00` | today=`False` | article_http=`HTTP 200` | https://www.whitehouse.gov/presidential-actions/2026/11/expeditious-enforcement-of-capital-sentences-and-the-pursuit-of-justice-for-victims-of-heinous-crimes/

### `us_axios` — Axios (US_media)
- Feed: `https://api.axios.com/feed/`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `100` | Today (2026-11-26): `YES` (6)
  1. **Macy's Thanksgiving parade postponed for the first time in the event's history** | pub_sh=`2026-11-26T05:28:25+08:00` | today=`True` | article_http=`HTTP 200` | https://www.axios.com/2026/11/25/macys-thanksgiving-parade-2026-balloons-weather
  2. **"The flashing red lights couldn't be brighter": Democrats demand new restrictions on AI** | pub_sh=`2026-11-26T04:19:21+08:00` | today=`True` | article_http=`HTTP 200` | https://www.axios.com/2026/11/25/democrats-ai-safety-restrictions-openai-anthropic-axios

### `us_wsj` — Wall Street Journal — US News (US_media)
- Feed: `https://feeds.content.dowjones.io/public/rss/RSSUSnews`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `40` | Today (2026-11-26): `YES` (9)
  1. **Macy’s Postpones Its Thanksgiving Day Parade Until Saturday** | pub_sh=`2026-11-26T07:38:00+08:00` | today=`True` | article_http=`HTTP 401` | https://www.wsj.com/us-news/macys-postpones-its-thanksgiving-day-parade-until-saturday-261dc15c?mod=rss_usnews
  2. **Opinion | Brace for the Trump-Warren Credit Card** | pub_sh=`2026-11-26T06:28:00+08:00` | today=`True` | article_http=`HTTP 401` | https://www.wsj.com/opinion/donald-trump-credit-card-interest-rate-cap-7c07e7ca?mod=rss_usnews

### `us_the_verge` — The Verge (US_tech)
- Feed: `https://www.theverge.com/rss/index.xml`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `10` | Today (2026-11-26): `YES` (10)
  1. **Now Google’s Familiar Faces AI feature works on Walmart’s $35 smart home camera too** | pub_sh=`2026-11-26T08:04:34+08:00` | today=`True` | article_http=`HTTP 200` | https://www.theverge.com/tech/1042938/google-home-familiar-faces-onn-cameras
  2. **Amazon loses its latest attempt to get out of handling more recall notices** | pub_sh=`2026-11-26T07:56:44+08:00` | today=`True` | article_http=`HTTP 200` | https://www.theverge.com/tech/1042870/amazon-recall-order-cpsc

### `us_mit_tech_review` — MIT Technology Review (US_tech)
- Feed: `https://www.technologyreview.com/feed/`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `10` | Today (2026-11-26): `YES` (1)
  1. **How data centers are driving a US natural-gas boom** | pub_sh=`2026-11-26T01:00:00+08:00` | today=`True` | article_http=`HTTP 200` | https://www.technologyreview.com/2026/11/25/1149836/data-centers-gas-power-plants/
  2. **The Download: AI swamping open records, and firefighting for permafrost** | pub_sh=`2026-11-25T21:10:00+08:00` | today=`False` | article_http=`HTTP 200` | https://www.technologyreview.com/2026/11/25/1149808/the-download-ai-open-records-permafrost-fires/

### `us_wired` — Wired (US_tech)
- Feed: `https://www.wired.com/feed/rss`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `50` | Today (2026-11-26): `YES` (1)
  1. **The Iowa Lead Detonation Happened. Now the Real Work Begins to Study It** | pub_sh=`2026-11-26T02:38:12+08:00` | today=`True` | article_http=`HTTP 200` | https://www.wired.com/story/iowa-lead-detonation-real-monitoring-work-begins/
  2. **The 30 Best Early Black Friday Deals: Our Ultimate Picks (2026)** | pub_sh=`2026-11-25T23:03:16+08:00` | today=`False` | article_http=`HTTP 200` | https://www.wired.com/story/best-black-friday-deals-11-25-2026/

### `in_the_hindu` — The Hindu — National (IN_media)
- Feed: `https://www.thehindu.com/news/national/feeder/default.rss`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `60` | Today (2026-11-26): `YES` (60)
  1. **Constitution Day LIVE updates: Priceless heritage of Indian democracy, says PM Modi** | pub_sh=`2026-11-26T12:18:05+08:00` | today=`True` | article_http=`HTTP 200` | https://www.thehindu.com/news/national/constitution-day-indian-democracy-pm-modi-congress-samvidhan-raksha-march-november-26-2026-live-updates/article71745137.ece
  2. **Karnataka charts India’s first comprehensive care and rehabilitation policy for burns survivors** | pub_sh=`2026-11-26T12:16:45+08:00` | today=`True` | article_http=`HTTP 200` | https://www.thehindu.com/news/national/karnataka/karnataka-charts-indias-first-comprehensive-care-and-rehabilitation-policy-for-burns-survivors/article71742493.ece

### `in_indian_express` — The Indian Express — India (IN_media)
- Feed: `https://indianexpress.com/section/india/feed/`
- HTTP: `403` | Content-Type: `text/html` | Entries: `0` | Today (2026-11-26): `NO` (0)
- Error: `HTTP 403`

### `in_ndtv` — NDTV — Top Stories (IN_media)
- Feed: `https://feeds.feedburner.com/ndtvnews-top-stories`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `YES` (20)
  1. **Assam Gets Northeast's First Defence Facility, Foundation Stone Laid** | pub_sh=`2026-11-26T12:13:56+08:00` | today=`True` | article_http=`HTTP 403` | https://www.ndtv.com/india-news/assam-gets-northeasts-first-defence-facility-foundation-stone-laid-cm-himanta-biswa-12378598#publisher=newsstand
  2. **Video: Stopped For Fancy Plate, Thar Driver Drags Pune Cop On Bonnet For 50 Feet** | pub_sh=`2026-11-26T12:13:06+08:00` | today=`True` | article_http=`HTTP 403` | https://www.ndtv.com/others-news/on-cctv-cop-dragged-50-feet-on-thar-bonnet-over-fancy-number-challan-in-maharashtra-baramati-12378356#publisher=newsstand

### `au_guardian` — The Guardian — Australia News (AU_media)
- Feed: `https://www.theguardian.com/australia-news/rss`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `YES` (8)
  1. **Australian politics live: Liberals ‘tossing up whether to leave or remain’, Albanese says; Coalition warns energy prices to cause Christmas ‘pain’** | pub_sh=`2026-11-26T12:09:57+08:00` | today=`True` | article_http=`HTTP 200` | https://www.theguardian.com/australia-news/live/2026/nov/26/labor-anthony-albanese-pauline-hanson-one-nation-angus-taylor-coalition-ntwnfb
  2. **Coalition would privatise Melbourne’s sewage treatment while selling state-owned land and renewables to fund Victorian election promises** | pub_sh=`2026-11-26T10:35:09+08:00` | today=`True` | article_http=`HTTP 200` | https://www.theguardian.com/australia-news/2026/nov/26/liberal-nationals-victoria-election-policy-costings-revealed-sewage-land-energy

### `au_guardian_pacific` — The Guardian — Pacific Islands (AU_media)
- Feed: `https://www.theguardian.com/world/pacific-islands/rss`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `NO` (0)
  1. **Why is France fighting Vanuatu over two uninhabited islands in the Pacific?** | pub_sh=`2026-11-25T07:47:38+08:00` | today=`False` | article_http=`HTTP 200` | https://www.theguardian.com/world/2026/nov/25/why-is-france-fighting-vanuatu-uninhabited-pacific-islands-icj
  2. **Queensland has a history of slavery. These unmarked graves tell Australia's dark history – video** | pub_sh=`2026-11-23T22:00:49+08:00` | today=`False` | article_http=`HTTP 200` | https://www.theguardian.com/world/video/2026/nov/24/queensland-has-a-history-of-slavery-these-unmarked-graves-tell-australia-dark-history-video-ntwnfb
