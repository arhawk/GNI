# WorldMonitor Native RSS & GDELT DOC 2.0 Probe Log

- Probe time (Asia/Shanghai): `2026-11-26T20:10:07.884074+08:00`
- Today window (Asia/Shanghai): `2026-11-26`
- Total probed: `11`

## Summary Table

| Group | source_id | Name | Type | Scope | HTTP | Entries | Today? | Today N | Latest (Shanghai) | Error |
|---|---|---|---|---|---:|---:|---|---:|---|---|
| DE_media | `de_tagesschau` | Tagesschau (ARD) | `public_service` | `GENERAL_NEWS` | 200 | 40 | YES | 32 | `2026-11-26T20:04:38+08:00` | — |
| DE_media | `de_spiegel` | Der Spiegel — Top News | `mainstream_independent` | `GENERAL_NEWS` | 200 | 23 | YES | 19 | `2026-11-26T19:51:00+08:00` | — |
| DE_media | `de_zeit` | Die Zeit — News | `mainstream_independent` | `GENERAL_NEWS` | 200 | 15 | YES | 15 | `2026-11-26T20:07:02+08:00` | — |
| DE_media | `de_dw_german` | Deutsche Welle (German all) | `public_service` | `GENERAL_NEWS` | 200 | 88 | YES | 6 | `2026-11-26T18:48:00+08:00` | — |
| IN_media | `in_toi_world` | Times of India — World | `mainstream_independent` | `INTERNATIONAL_NEWS` | 200 | 20 | YES | 18 | `2026-11-26T19:31:00+08:00` | — |
| IN_media | `in_ht_world` | Hindustan Times — World News | `mainstream_independent` | `INTERNATIONAL_NEWS` | 200 | 100 | YES | 100 | `2026-11-26T19:24:26+08:00` | — |
| IN_media | `in_et_news` | The Economic Times — News | `mainstream_independent` | `GENERAL_NEWS` | 200 | 50 | YES | 50 | `2026-11-26T19:48:21+08:00` | — |
| IN_media | `in_livemint_news` | Livemint — News | `mainstream_independent` | `GENERAL_NEWS` | 200 | 35 | YES | 27 | `2026-11-26T19:59:10+08:00` | — |
| IN_media | `in_ndtv` | NDTV — Top Stories | `mainstream_independent` | `GENERAL_NEWS` | 200 | 20 | YES | 20 | `2026-11-26T20:03:04+08:00` | — |
| US_china | `us_rfa_mandarin` | Radio Free Asia (Mandarin RSS) | `state_controlled` | `CHINA_FOCUSED` | 200 | 30 | YES | 1 | `2026-11-26T15:03:31+08:00` | — |
| US_china | `us_the_diplomat` | The Diplomat | `mainstream_independent` | `INTERNATIONAL_NEWS` | 200 | 96 | YES | 4 | `2026-11-26T04:17:42+08:00` | — |

## Sample 2 Items per Source

### `de_tagesschau` — Tagesschau (ARD) (DE_media)
- Feed: `https://www.tagesschau.de/xml/rss2/`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `40` | Today (2026-11-26): `YES` (32)
  1. **Marktbericht: Aktieninvestoren blicken vorsichtig nach vorn** | pub_sh=`2026-11-26T20:04:38+08:00` | today=`True` | article_http=`HTTP 200` | https://www.tagesschau.de/wirtschaft/finanzen/dax-erholung-chancen-risiken-100.html
  2. **Merz fordert weitere Kürzungen der EU-Finanzen** | pub_sh=`2026-11-26T19:58:32+08:00` | today=`True` | article_http=`HTTP 200` | https://www.tagesschau.de/ausland/europa/eu-haushalt-ukraine-100.html

### `de_spiegel` — Der Spiegel — Top News (DE_media)
- Feed: `https://www.spiegel.de/schlagzeilen/tops/index.rss`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `23` | Today (2026-11-26): `YES` (19)
  1. **Europa League: Unwetter zwingt Besiktas-Flieger zur Notlandung** | pub_sh=`2026-11-26T19:51:00+08:00` | today=`True` | article_http=`HTTP 200` | https://www.spiegel.de/sport/fussball/europa-league-unwetter-zwingt-besiktas-flieger-zur-notlandung-a-f963c468-7c20-425f-a9c5-f8a108938edd#ref=rss
  2. **Ägypten: Archäologen finden 3400 Jahre alten Fluch-Papyrus in Luxor** | pub_sh=`2026-11-26T19:46:00+08:00` | today=`True` | article_http=`HTTP 200` | https://www.spiegel.de/wissenschaft/aegypten-archaeologen-finden-3400-jahre-alten-fluch-papyrus-in-luxor-a-d67309b3-b060-42bd-aab1-2ebd4099a2b8#ref=rss

### `de_zeit` — Die Zeit — News (DE_media)
- Feed: `https://newsfeed.zeit.de/index`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `15` | Today (2026-11-26): `YES` (15)
  1. **Katholische Kirche: Missbrauchsopfer von Priester stehen 550.000 Euro Schmerzensgeld zu** | pub_sh=`2026-11-26T20:07:02+08:00` | today=`True` | article_http=`HTTP 403` | https://www.zeit.de/gesellschaft/zeitgeschehen/2026-11/missbrauch-koelner-bistum-zu-bisher-hoechstem-schmerzensgeld-verurteilt
  2. **Nach Sperrung: A3 nach schwerem Lkw-Unfall wieder frei** | pub_sh=`2026-11-26T20:05:05+08:00` | today=`True` | article_http=`HTTP 403` | https://www.zeit.de/news/2026-11/26/sperrung-der-a3-nach-schweren-lkw-unfall-dauert-noch-an

### `de_dw_german` — Deutsche Welle (German all) (DE_media)
- Feed: `https://rss.dw.com/rdf/rss-de-all`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `88` | Today (2026-11-26): `YES` (6)
  1. **Trump und Rutte: Putin soll Ukraine-Krieg nicht "ausweiten"** | pub_sh=`2026-11-26T18:48:00+08:00` | today=`True` | article_http=`HTTP 200` | https://www.dw.com/de/trump-und-rutte-putin-soll-ukraine-krieg-nicht-ausweiten/a-80058560?maca=de-rss-de-all-1119-rdf
  2. **Geldwäscheverdacht: Europaweite Razzien - 21 Festnahmen** | pub_sh=`2026-11-26T18:35:00+08:00` | today=`True` | article_http=`HTTP 200` | https://www.dw.com/de/geldwäscheverdacht-europaweite-razzien-21-festnahmen/a-80058496?maca=de-rss-de-all-1119-rdf

### `in_toi_world` — Times of India — World (IN_media)
- Feed: `https://timesofindia.indiatimes.com/rssfeeds/296589292.cms`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `YES` (18)
  1. **Court upholds order to move utility pole after years-long neighbour dispute** | pub_sh=`2026-11-26T19:31:00+08:00` | today=`True` | article_http=`HTTP 200` | https://timesofindia.indiatimes.com/world/us/two-connecticut-homeowners-went-to-court-in-2019-over-a-utility-pole-that-prevented-them-from-widening-their-driveway-seven-years-later-an-appeals-court-upheld-an-order-requiring-neighbours-to-authorise-removal/articleshow/136159256.cms
  2. **Titus O'Neil's foundation brings Thanksgiving meals to 500 Tampa families** | pub_sh=`2026-11-26T19:31:00+08:00` | today=`True` | article_http=`HTTP 200` | https://timesofindia.indiatimes.com/world/us/wwe-star-titus-oneil-grew-up-knowing-what-it-meant-to-need-food-assistance-his-foundation-has-now-teamed-with-a-tampa-charity-to-give-500-families-thanksgiving-boxes-each-containing-meals-for-four-to-six-people/articleshow/136160353.cms

### `in_ht_world` — Hindustan Times — World News (IN_media)
- Feed: `https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `100` | Today (2026-11-26): `YES` (100)
  1. **Global stocks rebound after AI sell-off as investors assess Trump's tariffs, oil prices and inflation risks** | pub_sh=`2026-11-26T19:24:26+08:00` | today=`True` | article_http=`HTTP 200` | https://www.hindustantimes.com/world-news/us-news/global-stocks-rebound-after-ai-sell-off-as-investors-assess-trumps-tariffs-oil-prices-and-inflation-risks-101795689444252.html
  2. **Pak high court bars deportation of Afghan female medical students** | pub_sh=`2026-11-26T18:57:00+08:00` | today=`True` | article_http=`HTTP 200` | https://www.hindustantimes.com/world-news/pak-high-court-bars-deportation-of-afghan-female-medical-students-101795690620666.html

### `in_et_news` — The Economic Times — News (IN_media)
- Feed: `https://economictimes.indiatimes.com/news/rssfeeds/1715249553.cms`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `50` | Today (2026-11-26): `YES` (50)
  1. **Nitin Gadkari announces Rs 1 lakh crore road projects for Bengal, promises 250-km Kolkata ring road** | pub_sh=`2026-11-26T19:48:21+08:00` | today=`True` | article_http=`HTTP 200` | https://economictimes.indiatimes.com/news/economy/infrastructure/nitin-gadkari-announces-rs-1-lakh-crore-road-projects-for-bengal-promises-250-km-kolkata-ring-road/articleshow/136190629.cms
  2. **Nikesh Arora on How AI Agents Could Disrupt a $1 Trillion Internet Economy | ET Conversations** | pub_sh=`2026-11-26T19:31:10+08:00` | today=`True` | article_http=`HTTP 200` | https://economictimes.indiatimes.com/news/short-videos/nikesh-arora-on-how-ai-agents-could-disrupt-a-1-trillion-internet-economy-et-conversations/videoshow/136190002.cms

### `in_livemint_news` — Livemint — News (IN_media)
- Feed: `https://www.livemint.com/rss/news`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `35` | Today (2026-11-26): `YES` (27)
  1. **Health ministry mandates insurance, bans fees for autism stem cell trials; sets 90-day approval deadline** | pub_sh=`2026-11-26T19:59:10+08:00` | today=`True` | article_http=`HTTP 200` | https://www.livemint.com/news/india/health-ministry-mandates-insurance-fee-ban-and-90-day-clearance-rules-for-autism-stem-cell-trials-11795687902584.html
  2. **Tukaram Mundhe effect? Gym removes protein powder display after FDA warning on unlicensed sales** | pub_sh=`2026-11-26T19:51:38+08:00` | today=`True` | article_http=`HTTP 200` | https://www.livemint.com/news/india/tukaram-mundhe-effect-gym-removes-protein-powder-display-after-fda-warning-on-unlicensed-sales-11795693393379.html

### `in_ndtv` — NDTV — Top Stories (IN_media)
- Feed: `https://feeds.feedburner.com/ndtvnews-top-stories`
- HTTP: `200` | Content-Type: `text/xml` | Entries: `20` | Today (2026-11-26): `YES` (20)
  1. **7th Suspect Arrested From Bihar In Cyber Fraud Case In Assam** | pub_sh=`2026-11-26T20:03:04+08:00` | today=`True` | article_http=`HTTP 403` | https://www.ndtv.com/india-news/7th-suspect-arrested-from-bihar-in-cyber-fraud-case-in-assam-12380721#publisher=newsstand
  2. **"Rs 5,000 A Month Till Graduates Can't Get Job": Akhilesh Yadav's UP Manifesto With Gen-Z Focus** | pub_sh=`2026-11-26T20:01:19+08:00` | today=`True` | article_http=`HTTP 403` | https://www.ndtv.com/india-news/rs-5-000-per-month-till-graduates-don-t-find-a-job-akhilesh-yadav-s-up-manifesto-12380519#publisher=newsstand

### `us_rfa_mandarin` — Radio Free Asia (Mandarin RSS) (US_china)
- Feed: `https://www.rfa.org/mandarin/rss`
- HTTP: `200` | Content-Type: `application/xml` | Entries: `30` | Today (2026-11-26): `YES` (1)
  1. **“选举本该如此”  当港人和中配走进选战** | pub_sh=`2026-11-26T15:03:31+08:00` | today=`True` | article_http=`HTTP 200` | https://rfa.org/mandarin/ytbdzhuantixilie/2026/11/26/taiwan-election-chinese-hongkonger/
  2. **陈吉宁遭调查 专家：21大人事添变数** | pub_sh=`2026-11-25T16:29:39+08:00` | today=`False` | article_http=`HTTP 200` | https://rfa.org/mandarin/yataibaodao/2026/11/25/chen-ji-ning-under-scrutiny/

### `us_the_diplomat` — The Diplomat (US_china)
- Feed: `https://thediplomat.com/feed/`
- HTTP: `200` | Content-Type: `application/rss+xml` | Entries: `96` | Today (2026-11-26): `YES` (4)
  1. **** | pub_sh=`2026-11-26T04:17:42+08:00` | today=`True` | article_http=`HTTP 200` | https://thediplomat.com
  2. **China’s Soft Espionage: The Technology Transfers That Don’t Make Headlines** | pub_sh=`2026-11-26T01:31:00+08:00` | today=`True` | article_http=`HTTP 200` | https://thediplomat.com/2026/11/chinas-soft-espionage-the-technology-transfers-that-dont-make-headlines/

## GDELT DOC 2.0 API Probe (`timespan=24h`, `maxrecords=20`)

| source_id | Country | HTTP | Articles | Top Domains | Error |
|---|---|---:|---:|---|---|
| `us_gdelt_china` | `US` | 429 | 0 | — | HTTP 429: Please limit requests to one every 5 seconds or contact kalev.leetaru5@gmail.com for larger queries. All high-traffic users should switch to our ngrams dataset: |
| `in_gdelt_china` | `IN` | 429 | 0 | — | HTTP 429: Please limit requests to one every 5 seconds or contact kalev.leetaru5@gmail.com for larger queries. All high-traffic users should switch to our ngrams dataset: |
| `de_gdelt_china` | `DE` | 429 | 0 | — | HTTP 429: Please limit requests to one every 5 seconds or contact kalev.leetaru5@gmail.com for larger queries. All high-traffic users should switch to our ngrams dataset: |

### `us_gdelt_china` (`(China OR Chinese OR Beijing OR Taiwan) sourcecountry:US`)

### `in_gdelt_china` (`(China OR Chinese OR Beijing OR Taiwan) sourcecountry:IN`)

### `de_gdelt_china` (`(China OR Chinese OR Beijing OR Taiwan) sourcecountry:GM`)
