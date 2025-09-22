"""Legacy entry point for running the Báscula Tk application."""

from bascula.ui.app import BasculaApp as BasculaAppTk


def main() -> None:
    app = BasculaAppTk()
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
