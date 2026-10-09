import argparse
import glob
import json
from pathlib import Path

from .db import connect, database_path, initialize
from .demo import seed_demo
from .importer import import_file
from .metrics import dashboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт отчётов 1С и проверка дашборда")
    parser.add_argument("--db", type=Path, default=database_path())
    commands = parser.add_subparsers(dest="command", required=True)
    importing = commands.add_parser("import", help="Импортировать XLSX; повторный импорт идемпотентен")
    importing.add_argument("files", nargs="+", help="Пути к файлам или glob-шаблоны")
    demo = commands.add_parser("seed-demo", help="Создать отдельную демонстрационную историю")
    demo.add_argument("--days", type=int, default=14)
    commands.add_parser("verify", help="Проверить сохранённые суммы")
    args = parser.parse_args()
    if args.command == "import":
        paths = []
        for pattern in args.files:
            matched = sorted(glob.glob(pattern))
            if not matched:
                parser.error(f"Файл не найден: {pattern}")
            paths.extend(Path(name) for name in matched)
        results = [import_file(path, args.db) for path in dict.fromkeys(paths)]
    elif args.command == "seed-demo":
        results = seed_demo(args.db, args.days)
    else:
        initialize(args.db)
        with connect(args.db) as conn:
            result = dashboard(conn, "actual", None, [])
        results = {"date": result["snapshot_date"], "totals": result["totals"],
                   "quality": result["quality"]}
        if not all(item["reconciled"] for item in result["quality"]):
            raise SystemExit("Контроль не сошёлся")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
