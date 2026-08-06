"""Pruebas básicas de la línea de comandos."""

from app.cli import build_parser, cmd_config, cmd_paper_status


class TestCli:
    def test_build_parser_includes_paper_commands(self) -> None:
        parser = build_parser()
        for command in ("paper-start", "paper-stop", "paper-status"):
            args = parser.parse_args([command])
            assert args.command == command

    def test_paper_status_no_scheduler(self, capsys) -> None:
        parser = build_parser()
        args = parser.parse_args(["paper-status"])
        result = cmd_paper_status(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "No hay paper trading" in captured.out

    def test_config_command(self, capsys) -> None:
        parser = build_parser()
        args = parser.parse_args(["config"])
        result = cmd_config(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "TRADING_MODE" in captured.out
