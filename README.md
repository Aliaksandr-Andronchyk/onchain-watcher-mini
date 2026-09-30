# onchain-watcher-mini

A minimal EVM on-chain watcher. It polls a chain over JSON-RPC, filters logs
by contract address and/or event topic, stores new matches in SQLite, and
sends a Telegram alert for each match.

## What it does

- Polls `eth_blockNumber` and `eth_getLogs` over any HTTP JSON-RPC endpoint.
- Filters by `--address`, `--topic`, or both.
- Persists every match in a SQLite database (dedup on tx hash + log index).
- Sends a Telegram message via Bot API when a new match is found.

## Run

```bash
pip install --upgrade pip  # stdlib only, no extra deps

python3 watcher.py \
  --rpc-url https://eth.llamarpc.com \
  --address 0xdAC17F958D2ee523a2206206994597C13D831ec \
  --db watcher.db \
  --tg-token "$TG_TOKEN" \
  --tg-chat-id "$TG_CHAT_ID"
```

One-shot mode (useful for testing or cron):

```bash
python3 watcher.py --rpc-url https://eth.llamarpc.com --address 0x... --once
```

## Flags

- `--rpc-url` (обязателен) – HTTP RPC endpoint EVM-цепи.
- `--address` – фильтр по адресу контракта.
- `--topic` – фильтр по topic0 события.
- `--db` – путь к SQLite базе находок (по умолчанию `watcher.db`).
- `--tg-token`, `--tg-chat-id` – токен и chat_id для Telegram-алертов.
- `--poll-interval` – пауза между опросами в секундах (по умолчанию `10`).
- `--once` – один проход без цикла (для теста или cron).
- `--start-block` – блок, с которого начать (по умолчанию – текущий).

## Test

```bash
python3 -m unittest test_watcher.py -v
```
