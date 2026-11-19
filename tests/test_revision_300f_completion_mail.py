"""300f (reported 2026-11-18): web runs did not send the completion e-mail
that Voila sends. The SMTP server stayed at the engine's built-in
"localhost" and the notification address was empty unless filled in. When a
run starts, the server's DEFAULT_SMTP_SERVER is used, and an empty address
takes DEFAULT_NOTIFICATION_EMAIL, as Voila prefills it. Tests never send mail."""
import os
from types import SimpleNamespace

from JBGProjectRuns import apply_mail_settings


def _config(address=""):
    return SimpleNamespace(mail=SimpleNamespace(smtp_server="localhost",
                                                notification_email=address))


def test_the_servers_settings_are_used():
    config = _config()
    apply_mail_settings(config, {"DEFAULT_SMTP_SERVER": "smtp.example.org",
                                 "DEFAULT_NOTIFICATION_EMAIL": "team@example.org"})
    assert (config.mail.smtp_server, config.mail.notification_email) == \
        ("smtp.example.org", "team@example.org")


def test_an_address_the_configuration_sets_is_kept():
    config = _config("me@example.org")
    apply_mail_settings(config, {"DEFAULT_SMTP_SERVER": "smtp.example.org",
                                 "DEFAULT_NOTIFICATION_EMAIL": "team@example.org"})
    assert config.mail.notification_email == "me@example.org"


def test_without_server_settings_nothing_changes():
    config = _config()
    apply_mail_settings(config, {})
    assert (config.mail.smtp_server, config.mail.notification_email) == ("localhost", "")


def test_every_run_configuration_gets_them_and_tests_send_no_mail():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "src" / "JBGProjectRuns.py").read_text(
        encoding="utf-8")
    load = source.split("def _load_config(settings: dict):")[1].split("\ndef ")[0]
    assert "apply_mail_settings(config)" in load
    assert os.environ["DEFAULT_SMTP_SERVER"] == "" and os.environ["DEFAULT_NOTIFICATION_EMAIL"] == ""
