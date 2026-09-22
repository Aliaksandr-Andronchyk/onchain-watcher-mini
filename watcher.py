#!/usr/bin/env python3
import argparse
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "watcher.db"


def rpc_call(rpc_url: str, method: str, params: list, timeout: int = 15) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        rpc_url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    if "error" in body:
        raise RuntimeError(body["error"])
    return body["result"]


def get_block_number(rpc_url: str) -> int:
    return int(rpc_call(rpc_url, "eth_blockNumber", []), 16)


def get_logs(rpc_url: str, from_block: int, to_block: int, address: str | None, topic: str | None) -> list:
    params = {
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
    }
    if address:
        params["address"] = address
    if topic:
        params["topics"] = [topic]
    return rpc_call(rpc_url, "eth_getLogs", [params])


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS находки (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_number INTEGER NOT NULL,
            tx_hash TEXT NOT NULL,
            log_index INTEGER NOT NULL,
            address TEXT NOT NULL,
            topics TEXT NOT NULL,
            data TEXT NOT NULL,
            найдено_в TEXT NOT NULL,
            UNIQUE(tx_hash, log_index)
        )
        """
    )
    conn.commit()
    return conn


def save_log(conn: sqlite3.Connection, log: dict) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO находки (block_number, tx_hash, log_index, address, topics, data, найдено_в)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                int(log["blockNumber"], 16),
                log["transactionHash"],
                int(log["logIndex"], 16),
                log["address"],
                json.dumps(log["topics"]),
                log["data"],
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def send_telegram_alert(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def format_alert(log: dict) -> str:
    return (
        "Найдено совпадение\n"
        f"блок: {int(log['blockNumber'], 16)}\n"
        f"адрес: {log['address']}\n"
        f"tx: {log['transactionHash']}\n"
        f"topic0: {log['topics'][0] if log['topics'] else '-'}"
    )


def run(
    rpc_url: str,
    address: str | None,
    topic: str | None,
    db_path: Path,
    tg_token: str | None,
    tg_chat_id: str | None,
    poll_interval: float,
    once: bool,
    start_block: int | None,
) -> None:
    conn = init_db(db_path)
    if start_block is not None:
        last_block = start_block
    else:
        head_now = get_block_number(rpc_url)
        last_block = head_now - 1 if once else head_now

    while True:
        head = get_block_number(rpc_url)
        if head > last_block:
            logs = get_logs(rpc_url, last_block + 1, head, address, topic)
            for log in logs:
                is_new = save_log(conn, log)
                if is_new:
                    print(format_alert(log))
                    if tg_token and tg_chat_id:
                        send_telegram_alert(tg_token, tg_chat_id, format_alert(log))
            last_block = head

        if once:
            break
        time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ончейн-вотчер: слушает логи EVM-цепи по RPC")
    parser.add_argument("--rpc-url", required=True, help="HTTP RPC endpoint EVM-цепи")
    parser.add_argument("--address", help="фильтр по адресу контракта")
    parser.add_argument("--topic", help="фильтр по topic0 события")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="путь к SQLite базе находок")
    parser.add_argument("--tg-token", help="токен Telegram-бота для алертов")
    parser.add_argument("--tg-chat-id", help="chat_id для алертов")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="пауза между опросами, сек")
    parser.add_argument("--once", action="store_true", help="один проход без цикла (для теста)")
    parser.add_argument("--start-block", type=int, help="блок, с которого начать (по умолчанию – текущий)")
    args = parser.parse_args()

    if not args.address and not args.topic:
        parser.error("нужен хотя бы один фильтр: --address или --topic")

    run(
        rpc_url=args.rpc_url,
        address=args.address,
        topic=args.topic,
        db_path=Path(args.db),
        tg_token=args.tg_token,
        tg_chat_id=args.tg_chat_id,
        poll_interval=args.poll_interval,
        once=args.once,
        start_block=args.start_block,
    )


if __name__ == "__main__":
    main()
