import pytest

from app.settings import garden_login_limits


def test_garden_login_limits_default_to_5_failures_in_15_minutes(monkeypatch):
    monkeypatch.delenv("GARDEN_LOGIN_MAX_FAILURES", raising=False)
    monkeypatch.delenv("GARDEN_LOGIN_WINDOW_MINUTES", raising=False)
    assert garden_login_limits() == (5, 15)
    monkeypatch.setenv("GARDEN_LOGIN_MAX_FAILURES", " ")  # 空は未設定と同じ
    assert garden_login_limits() == (5, 15)


def test_garden_login_limits_can_be_set(monkeypatch):
    monkeypatch.setenv("GARDEN_LOGIN_MAX_FAILURES", "10")
    monkeypatch.setenv("GARDEN_LOGIN_WINDOW_MINUTES", "30")
    assert garden_login_limits() == (10, 30)


@pytest.mark.parametrize("name", ["GARDEN_LOGIN_MAX_FAILURES", "GARDEN_LOGIN_WINDOW_MINUTES"])
@pytest.mark.parametrize("value", ["abc", "1.5", "0", "-3", "99999999"])
def test_garden_login_limits_reject_bad_values_without_echoing_them(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError) as excinfo:
        garden_login_limits()
    message = str(excinfo.value)
    assert message.startswith(name)
    if value in ("abc", "1.5", "99999999"):  # 範囲の数字（1000 など）と紛れない値だけ、本文に出ていないことを確かめる
        assert value not in message
