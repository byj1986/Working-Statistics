from pathlib import Path
from utils.miscellaneous import get_startup_dir, get_pythonw_path, create_shortcut


def main():
    script_dir = Path(__file__).resolve().parent
    startup_dir = get_startup_dir()
    startup_dir.mkdir(parents=True, exist_ok=True)
    pythonw = get_pythonw_path()
    server_py = script_dir / "server.py"
    link_path = startup_dir / "start_view_data_statistics.lnk"
    icon_path = script_dir / "statistics.ico"
    args_expr = f'Chr(34) & "{str(server_py)}" & Chr(34)'
    create_shortcut(link_path, pythonw, args_expr, script_dir, icon_path)
    print(str(link_path))


if __name__ == "__main__":
    main()
