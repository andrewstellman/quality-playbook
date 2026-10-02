# GPT control run log

| Model | Repository | Run | Start / finish (UTC) | Defects reported | Problems |
| --- | --- | --- | --- | ---: | --- |
| gpt-6-sol | aiohttp | 01 | started before 2026-09-28 21:45:47 UTC (exact time not captured); finished 2026-09-28 21:47:12 UTC | 4 | missing multidict prevented runtime reproduction |
| gpt-6-sol | aiohttp | 02 | started before 2026-09-28 21:45:47 UTC (exact time not captured); finished 2026-09-28 21:47:20 UTC | 3 | missing multidict prevented runtime reproduction |
| gpt-6-sol | aiohttp | 03 | started before 2026-09-28 21:45:47 UTC (exact time not captured); finished 2026-09-28 21:47:22 UTC | 3 | missing multidict prevented runtime reproduction |
| gpt-6-sol | aiohttp | 04 | started approximately 2026-09-28 21:48:26 UTC; finished 2026-09-28 21:50:10 UTC | 2 | missing multidict prevented package tests |
| gpt-6-sol | aiohttp | 05 | started approximately 2026-09-28 21:48:26 UTC; finished 2026-09-28 21:50:17 UTC | 3 | missing yarl prevented runtime reproduction |
| gpt-6-sol | aiohttp | 06 | started approximately 2026-09-28 21:48:26 UTC; finished 2026-09-28 21:51:04 UTC | 3 | missing multidict prevented runtime reproduction |
| gpt-6-sol | aiohttp | 07 | started approximately 2026-09-28 21:50:32 UTC; finished 2026-09-28 21:53:00 UTC | 4 | missing multidict prevented runtime verification |
| gpt-6-sol | aiohttp | 08 | started approximately 2026-09-28 21:50:32 UTC; finished 2026-09-28 21:52:57 UTC | 3 | missing multidict prevented runtime verification |
| gpt-6-sol | aiohttp | 09 | started approximately 2026-09-28 21:51:19 UTC; finished 2026-09-28 21:53:05 UTC | 5 | missing multidict prevented runtime verification |
| gpt-6-sol | aiohttp | 10 | started approximately 2026-09-28 21:53:07 UTC; finished 2026-09-28 21:55:54 UTC | 4 | missing multidict prevented package tests |
| gpt-6-sol | chi | 01 | started approximately 2026-09-28 21:53:27 UTC; finished 2026-09-28 21:55:37 UTC | 4 | full package tests blocked by sandbox listening-socket restriction |
| gpt-6-sol | chi | 02 | started approximately 2026-09-28 21:53:27 UTC; finished 2026-09-28 21:56:02 UTC | 4 | none reported |
| gpt-6-sol | chi | 03 | started approximately 2026-09-28 21:55:47 UTC; finished 2026-09-28 21:58:23 UTC | 4 | full tests blocked by sandbox TCP-listener restriction |
| gpt-6-sol | chi | 04 | started approximately 2026-09-28 21:56:08 UTC; finished 2026-09-28 21:58:49 UTC | 6 | none reported |
| gpt-6-sol | chi | 05 | started approximately 2026-09-28 21:56:49 UTC; finished 2026-09-28 21:58:53 UTC | 5 | none reported |
| gpt-6-sol | chi | 06 | started approximately 2026-09-28 21:58:32 UTC; finished 2026-09-28 22:01:09 UTC | 5 | none reported |
| gpt-6-sol | chi | 07 | started approximately 2026-09-28 21:59:16 UTC; finished 2026-09-28 22:01:37 UTC | 4 | none reported |
| gpt-6-sol | chi | 08 | started approximately 2026-09-28 21:59:16 UTC; finished 2026-09-28 22:00:45 UTC | 4 | none reported |
| gpt-6-sol | chi | 09 | started approximately 2026-09-28 22:01:02 UTC; finished 2026-09-28 22:03:42 UTC | 7 | none reported |
| gpt-6-sol | chi | 10 | started approximately 2026-09-28 22:01:19 UTC; finished 2026-09-28 22:03:34 UTC | 5 | none reported |
| gpt-6-sol | express | 01 | started approximately 2026-09-28 22:01:48 UTC; finished 2026-09-28 22:03:26 UTC | 1 | Express tests unavailable because dependencies are absent |
| gpt-6-sol | express | 02 | started approximately 2026-09-28 22:03:39 UTC; finished 2026-09-28 22:05:49 UTC | 2 | Express dependencies absent |
| gpt-6-sol | express | 03 | started approximately 2026-09-28 22:03:39 UTC; finished 2026-09-28 22:05:16 UTC | 1 | Express dependencies absent |
| gpt-6-sol | express | 04 | started approximately 2026-09-28 22:04:10 UTC; finished 2026-09-28 22:06:07 UTC | 2 | Express dependencies absent |
| gpt-6-sol | express | 05 | started approximately 2026-09-28 22:05:33 UTC; finished 2026-09-28 22:07:22 UTC | 2 | Express dependencies absent |
| gpt-6-sol | express | 06 | started approximately 2026-09-28 22:06:00 UTC; finished 2026-09-28 22:07:43 UTC | 2 | Express dependencies absent |
| gpt-6-sol | express | 07 | started approximately 2026-09-28 22:06:15 UTC; finished 2026-09-28 22:07:57 UTC | 1 | Express dependencies absent |
| gpt-6-sol | express | 08 | started approximately 2026-09-28 22:07:49 UTC; finished 2026-09-28 22:10:25 UTC | 2 | dependencies absent; sandbox socket-listen restriction |
| gpt-6-sol | express | 09 | started approximately 2026-09-28 22:08:14 UTC; finished 2026-09-28 22:09:41 UTC | 1 | none reported |
| gpt-6-sol | express | 10 | started approximately 2026-09-28 22:08:14 UTC; finished 2026-09-28 22:10:37 UTC | 1 | dependencies absent |
| gpt-6-sol | otel | 01 | started approximately 2026-09-28 22:11:02 UTC; finished 2026-09-28 22:12:57 UTC | 5 | none reported |
| gpt-6-sol | otel | 02 | started approximately 2026-09-28 22:13:22 UTC; finished 2026-09-28 22:17:15 UTC | 6 | none reported |
| gpt-6-sol | otel | 03 | started approximately 2026-09-28 22:17:28 UTC; finished 2026-09-28 22:19:30 UTC | 4 | none reported |
| gpt-6-sol | otel | 04 | started approximately 2026-09-28 22:19:50 UTC; finished 2026-09-28 22:21:31 UTC | 4 | none reported |
| gpt-6-sol | otel | 05 | started approximately 2026-09-28 22:21:55 UTC; finished 2026-09-28 22:23:37 UTC | 5 | none reported |
| gpt-6-sol | otel | 06 | started approximately 2026-09-28 22:23:53 UTC; finished 2026-09-28 22:26:10 UTC | 5 | none reported |
| gpt-6-sol | otel | 07 | started approximately 2026-09-28 22:26:22 UTC; finished 2026-09-28 22:28:57 UTC | 4 | none reported |
| gpt-6-sol | otel | 08 | started approximately 2026-09-28 22:29:17 UTC; finished 2026-09-28 22:31:10 UTC | 4 | none reported |
| gpt-6-sol | otel | 09 | started approximately 2026-09-28 22:31:27 UTC; finished 2026-09-28 22:34:39 UTC | 6 | none reported |
| gpt-6-sol | otel | 10 | started approximately 2026-09-28 22:34:51 UTC; finished 2026-09-28 22:37:08 UTC | 5 | none reported |
| gpt-6-sol | assertj | 01 | started approximately 2026-09-28 22:37:22 UTC; finished 2026-09-28 22:39:20 UTC | 5 | none reported |
| gpt-6-sol | assertj | 02 | started approximately 2026-09-28 22:39:35 UTC; finished 2026-09-28 22:42:15 UTC | 5 | none reported |
| gpt-6-sol | assertj | 03 | started approximately 2026-09-28 22:42:27 UTC; finished 2026-09-28 22:44:20 UTC | 5 | none reported |
| gpt-6-sol | assertj | 04 | started approximately 2026-09-28 22:44:29 UTC; finished 2026-09-28 22:46:23 UTC | 5 | none reported |
| gpt-6-sol | assertj | 05 | started approximately 2026-09-28 22:46:36 UTC; finished 2026-09-28 22:49:11 UTC | 5 | none reported |
| gpt-6-sol | assertj | 06 | started approximately 2026-09-28 22:49:30 UTC; finished 2026-09-28 22:51:09 UTC | 4 | none reported |
| gpt-6-sol | assertj | 07 | started approximately 2026-09-28 22:51:20 UTC; finished 2026-09-28 22:53:26 UTC | 5 | none reported |
| gpt-6-sol | assertj | 08 | started approximately 2026-09-28 22:53:45 UTC; finished 2026-09-28 22:55:49 UTC | 5 | none reported |
| gpt-6-sol | assertj | 09 | started approximately 2026-09-28 22:55:57 UTC; finished 2026-09-28 22:58:37 UTC | 4 | none reported |
| gpt-6-sol | assertj | 10 | started approximately 2026-09-28 22:58:44 UTC; finished 2026-09-28 23:01:06 UTC | 5 | none reported |
| gpt-6-sol | calibre | 01 | started approximately 2026-09-28 23:01:26 UTC; finished 2026-09-28 23:03:20 UTC | 4 | none reported |
| gpt-6-sol | calibre | 02 | started approximately 2026-09-28 23:03:36 UTC; finished 2026-09-28 23:05:33 UTC | 3 | none reported |
| gpt-6-sol | calibre | 03 | started approximately 2026-09-28 23:05:43 UTC; finished 2026-09-28 23:07:22 UTC | 5 | none reported |
| gpt-6-sol | calibre | 04 | started approximately 2026-09-28 23:07:38 UTC; finished 2026-09-28 23:09:15 UTC | 2 | calibre import requires sys.extensions_location |
| gpt-6-sol | calibre | 05 | started approximately 2026-09-28 23:09:37 UTC; finished 2026-09-28 23:11:46 UTC | 2 | none reported |
| gpt-6-sol | calibre | 06 | started approximately 2026-09-28 23:12:05 UTC; finished 2026-09-28 23:13:32 UTC | 2 | none reported |
| gpt-6-sol | calibre | 07 | started approximately 2026-09-28 23:13:53 UTC; finished 2026-09-28 23:15:59 UTC | 3 | none reported |
| gpt-6-sol | calibre | 08 | started approximately 2026-09-28 23:16:13 UTC; finished 2026-09-28 23:19:14 UTC | 5 | checkout requires calibre built runtime unavailable to system Python |
| gpt-6-sol | calibre | 09 | started approximately 2026-09-28 23:19:35 UTC; finished 2026-09-28 23:22:15 UTC | 2 | none reported |
| gpt-6-sol | calibre | 10 | started approximately 2026-09-28 23:22:22 UTC; finished 2026-09-28 23:24:04 UTC | 3 | none reported |
| gpt-6-sol | bionemo | 01 | started approximately 2026-09-28 23:24:31 UTC; finished 2026-09-28 23:27:03 UTC | 4 | PyTorch unavailable in active environment |
| gpt-6-sol | bionemo | 02 | started approximately 2026-09-28 23:27:14 UTC; finished 2026-09-28 23:28:39 UTC | 4 | none reported |
| gpt-6-sol | bionemo | 03 | started approximately 2026-09-28 23:28:53 UTC; finished 2026-09-28 23:30:35 UTC | 3 | none reported |
| gpt-6-sol | bionemo | 04 | started approximately 2026-09-28 23:30:45 UTC; finished 2026-09-28 23:33:26 UTC | 4 | PyTorch unavailable |
| gpt-6-sol | bionemo | 05 | started approximately 2026-09-28 23:33:40 UTC; finished 2026-09-28 23:35:37 UTC | 4 | torch unavailable in local Python environment |
| gpt-6-sol | bionemo | 06 | started approximately 2026-09-28 23:35:47 UTC; finished 2026-09-28 23:37:33 UTC | 3 | none reported |
| gpt-6-sol | bionemo | 07 | started approximately 2026-09-28 23:37:40 UTC; finished 2026-09-28 23:40:26 UTC | 4 | Python dependencies unavailable |
| gpt-6-sol | bionemo | 08 | started approximately 2026-09-28 23:40:42 UTC; finished 2026-09-28 23:42:40 UTC | 4 | torch unavailable in local Python environment |
| gpt-6-sol | bionemo | 09 | started approximately 2026-09-28 23:43:00 UTC; finished 2026-09-28 23:45:16 UTC | 4 | torch not installed |
| gpt-6-sol | bionemo | 10 | started approximately 2026-09-28 23:45:23 UTC; finished 2026-09-28 23:47:10 UTC | 3 | none reported |
| gpt-5.6-terra | aiohttp | 01 | started approximately 2026-09-28 22:09:54 UTC; finished 2026-09-28 22:12:41 UTC | 3 | missing multidict prevented executable confirmation |
| gpt-5.6-terra | aiohttp | 02 | started approximately 2026-09-28 22:11:02 UTC; finished 2026-09-28 22:15:55 UTC | 4 | none reported |
| gpt-5.6-terra | aiohttp | 03 | started approximately 2026-09-28 22:12:53 UTC; finished 2026-09-28 22:16:48 UTC | 4 | none reported |
| gpt-5.6-terra | aiohttp | 04 | started approximately 2026-09-28 22:16:06 UTC; finished 2026-09-28 22:19:11 UTC | 3 | none reported |
| gpt-5.6-terra | aiohttp | 05 | started approximately 2026-09-28 22:17:02 UTC; finished 2026-09-28 22:20:47 UTC | 3 | none reported |
| gpt-5.6-terra | aiohttp | 06 | started approximately 2026-09-28 22:19:21 UTC; finished 2026-09-28 22:22:29 UTC | 2 | none reported |
| gpt-5.6-terra | aiohttp | 07 | started approximately 2026-09-28 22:21:01 UTC; finished 2026-09-28 22:23:46 UTC | 3 | none reported |
| gpt-5.6-terra | aiohttp | 08 | started approximately 2026-09-28 22:22:38 UTC; finished 2026-09-28 22:27:49 UTC | 4 | none reported |
| gpt-5.6-terra | aiohttp | 09 | started approximately 2026-09-28 22:24:10 UTC; finished 2026-09-28 22:26:32 UTC | 3 | none reported |
| gpt-5.6-terra | aiohttp | 10 | started approximately 2026-09-28 22:26:42 UTC; finished 2026-09-28 22:31:29 UTC | 2 | none reported |
| gpt-5.6-terra | chi | 01 | started approximately 2026-09-28 22:28:15 UTC; finished 2026-09-28 22:31:50 UTC | 4 | none reported |
| gpt-5.6-terra | chi | 02 | started approximately 2026-09-28 22:31:49 UTC; finished 2026-09-28 22:35:28 UTC | 4 | none reported |
| gpt-5.6-terra | chi | 03 | started approximately 2026-09-28 22:32:11 UTC; finished 2026-09-28 22:35:08 UTC | 5 | none reported |
| gpt-5.6-terra | chi | 04 | started approximately 2026-09-28 22:35:30 UTC; finished 2026-09-28 22:37:10 UTC | 2 | none reported |
| gpt-5.6-terra | chi | 05 | started approximately 2026-09-28 22:35:44 UTC; finished 2026-09-28 22:38:03 UTC | 4 | none reported |
| gpt-5.6-terra | chi | 06 | started approximately 2026-09-28 22:37:22 UTC; finished 2026-09-28 22:39:23 UTC | 2 | none reported |
| gpt-5.6-terra | chi | 07 | started approximately 2026-09-28 22:38:16 UTC; finished 2026-09-28 22:41:36 UTC | 3 | none reported |
| gpt-5.6-terra | chi | 08 | started approximately 2026-09-28 22:39:35 UTC; finished 2026-09-28 22:42:21 UTC | 3 | none reported |
| gpt-5.6-terra | chi | 09 | started approximately 2026-09-28 22:41:47 UTC; finished 2026-09-28 22:45:50 UTC | 3 | none reported |
| gpt-5.6-terra | chi | 10 | started approximately 2026-09-28 22:42:40 UTC; finished 2026-09-28 22:45:29 UTC | 6 | none reported |
| gpt-5.6-terra | express | 01 | started approximately 2026-09-28 22:45:42 UTC; finished 2026-09-28 22:48:19 UTC | 1 | none reported |
| gpt-5.6-terra | express | 02 | started approximately 2026-09-28 22:46:07 UTC; finished 2026-09-28 22:48:11 UTC | 1 | none reported |
| gpt-5.6-terra | express | 03 | started approximately 2026-09-28 22:48:16 UTC; finished 2026-09-28 22:49:49 UTC | 1 | none reported |
| gpt-5.6-terra | express | 04 | started approximately 2026-09-28 22:48:30 UTC; finished 2026-09-28 22:50:38 UTC | 1 | none reported |
| gpt-5.6-terra | express | 05 | started approximately 2026-09-28 22:50:07 UTC; finished 2026-09-28 22:52:15 UTC | 1 | none reported |
| gpt-5.6-terra | express | 06 | started approximately 2026-09-28 22:50:48 UTC; finished 2026-09-28 22:52:59 UTC | 1 | none reported |
| gpt-5.6-terra | express | 07 | started approximately 2026-09-28 22:52:26 UTC; finished 2026-09-28 22:54:26 UTC | 1 | none reported |
| gpt-5.6-terra | express | 08 | started approximately 2026-09-28 22:53:10 UTC; finished 2026-09-28 22:54:51 UTC | 1 | none reported |
| gpt-5.6-terra | express | 09 | started approximately 2026-09-28 22:54:36 UTC; finished 2026-09-28 22:56:33 UTC | 0 | none reported |
| gpt-5.6-terra | express | 10 | started approximately 2026-09-28 22:55:04 UTC; finished 2026-09-28 22:57:25 UTC | 1 | none reported |
| gpt-5.6-terra | otel | 01 | started approximately 2026-09-28 22:56:44 UTC; finished 2026-09-28 23:00:05 UTC | 3 | none reported |
| gpt-5.6-terra | otel | 02 | started approximately 2026-09-28 22:57:31 UTC; finished 2026-09-28 23:00:20 UTC | 4 | none reported |
| gpt-5.6-terra | otel | 03 | started approximately 2026-09-28 23:00:19 UTC; finished 2026-09-28 23:03:50 UTC | 3 | none reported |
| gpt-5.6-terra | otel | 04 | started approximately 2026-09-28 23:00:42 UTC; finished 2026-09-28 23:03:41 UTC | 5 | none reported |
| gpt-5.6-terra | otel | 05 | started approximately 2026-09-28 23:04:22 UTC; finished 2026-09-28 23:07:41 UTC | 5 | none reported |
| gpt-5.6-terra | otel | 06 | started approximately 2026-09-28 23:04:22 UTC; finished 2026-09-28 23:08:26 UTC | 5 | none reported |
| gpt-5.6-terra | otel | 07 | started approximately 2026-09-28 23:08:00 UTC; finished 2026-09-28 23:11:21 UTC | 5 | none reported |
| gpt-5.6-terra | otel | 08 | started approximately 2026-09-28 23:08:42 UTC; finished 2026-09-28 23:11:12 UTC | 4 | none reported |
| gpt-5.6-terra | otel | 09 | started approximately 2026-09-28 23:11:25 UTC; finished 2026-09-28 23:15:11 UTC | 4 | none reported |
| gpt-5.6-terra | otel | 10 | started approximately 2026-09-28 23:11:43 UTC; finished 2026-09-28 23:15:04 UTC | 5 | none reported |
| gpt-5.6-terra | assertj | 01 | started approximately 2026-09-28 23:15:21 UTC; finished 2026-09-28 23:17:44 UTC | 3 | none reported |
| gpt-5.6-terra | assertj | 02 | started approximately 2026-09-28 23:15:36 UTC; finished 2026-09-28 23:18:58 UTC | 3 | none reported |
| gpt-5.6-terra | assertj | 03 | started approximately 2026-09-28 23:17:59 UTC; finished 2026-09-28 23:21:29 UTC | 5 | none reported |
| gpt-5.6-terra | assertj | 04 | started approximately 2026-09-28 23:19:08 UTC; finished 2026-09-28 23:21:13 UTC | 3 | none reported |
| gpt-5.6-terra | assertj | 05 | started approximately 2026-09-28 23:21:22 UTC; finished 2026-09-28 23:23:49 UTC | 3 | none reported |
| gpt-5.6-terra | assertj | 06 | started approximately 2026-09-28 23:21:43 UTC; finished 2026-09-28 23:24:12 UTC | 4 | none reported |
| gpt-5.6-terra | assertj | 07 | started approximately 2026-09-28 23:23:59 UTC; finished 2026-09-28 23:25:51 UTC | 3 | none reported |
| gpt-5.6-terra | assertj | 08 | started approximately 2026-09-28 23:24:31 UTC; finished 2026-09-28 23:27:43 UTC | 4 | none reported |
| gpt-5.6-terra | assertj | 09 | started approximately 2026-09-28 23:25:58 UTC; finished 2026-09-28 23:27:41 UTC | 3 | none reported |
| gpt-5.6-terra | assertj | 10 | started approximately 2026-09-28 23:28:04 UTC; finished 2026-09-28 23:30:54 UTC | 2 | none reported |
| gpt-5.6-terra | calibre | 01 | started approximately 2026-09-28 23:28:04 UTC; finished 2026-09-28 23:31:04 UTC | 3 | none reported |
| gpt-5.6-terra | calibre | 02 | started approximately 2026-09-28 23:31:12 UTC; finished 2026-09-28 23:33:56 UTC | 4 | none reported |
| gpt-5.6-terra | calibre | 03 | started approximately 2026-09-28 23:31:29 UTC; finished 2026-09-28 23:34:19 UTC | 4 | none reported |
| gpt-5.6-terra | calibre | 04 | started approximately 2026-09-28 23:34:08 UTC; finished 2026-09-28 23:37:01 UTC | 4 | none reported |
| gpt-5.6-terra | calibre | 05 | started approximately 2026-09-28 23:34:31 UTC; finished 2026-09-28 23:37:18 UTC | 4 | none reported |
| gpt-5.6-terra | calibre | 06 | started approximately 2026-09-28 23:37:19 UTC; finished 2026-09-28 23:40:12 UTC | 5 | none reported |
| gpt-5.6-terra | calibre | 07 | started approximately 2026-09-28 23:37:40 UTC; finished 2026-09-28 23:41:34 UTC | 3 | none reported |
| gpt-5.6-terra | calibre | 08 | started approximately 2026-09-28 23:40:24 UTC; finished 2026-09-28 23:42:29 UTC | 2 | none reported |
| gpt-5.6-terra | calibre | 09 | started approximately 2026-09-28 23:41:45 UTC; finished 2026-09-28 23:45:16 UTC | 2 | none reported |
| gpt-5.6-terra | calibre | 10 | started approximately 2026-09-28 23:42:42 UTC; finished 2026-09-28 23:45:48 UTC | 5 | none reported |
| gpt-5.6-terra | bionemo | 01 | started approximately 2026-09-28 23:45:23 UTC; finished 2026-09-28 23:48:51 UTC | 1 | none reported |
| gpt-5.6-terra | bionemo | 02 | started approximately 2026-09-28 23:46:08 UTC; finished 2026-09-28 23:48:11 UTC | 3 | none reported |
| gpt-5.6-terra | bionemo | 03 | started approximately 2026-09-28 23:47:29 UTC; finished 2026-09-28 23:50:20 UTC | 3 | none reported |
| gpt-5.6-terra | bionemo | 04 | started approximately 2026-09-28 23:49:24 UTC; finished 2026-09-28 23:51:57 UTC | 5 | none reported |
| gpt-5.6-terra | bionemo | 05 | started approximately 2026-09-28 23:49:53 UTC; finished 2026-09-28 23:52:25 UTC | 4 | none reported |
| gpt-5.6-terra | bionemo | 06 | started approximately 2026-09-28 23:50:39 UTC; finished 2026-09-28 23:53:09 UTC | 4 | none reported |
| gpt-5.6-terra | bionemo | 07 | started approximately 2026-09-28 23:52:16 UTC; finished 2026-09-28 23:54:50 UTC | 2 | none reported |
| gpt-5.6-terra | bionemo | 08 | started approximately 2026-09-28 23:52:46 UTC; finished 2026-09-28 23:55:44 UTC | 3 | none reported |
| gpt-5.6-terra | bionemo | 09 | started approximately 2026-09-28 23:53:28 UTC; finished 2026-09-28 23:56:07 UTC | 4 | none reported |
| gpt-5.6-terra | bionemo | 10 | started approximately 2026-09-28 23:55:11 UTC; finished 2026-09-28 23:57:21 UTC | 3 | none reported |
