"""Sign-in: password rules, sessions, lockout after 5 wrong tries."""
import pytest

from app import auth, db


@pytest.fixture
def user(clean):
    db.run("DELETE FROM users")
    db.run("DELETE FROM sessions")
    db.run("DELETE FROM login_attempts")
    auth.create_user("kemmachat", "a-good-password")
    return "kemmachat"


def test_password_rules(clean):
    with pytest.raises(ValueError):
        auth.validate_new("ab", "a-good-password")
    with pytest.raises(ValueError):
        auth.validate_new("kemmachat", "short")


def test_hash_is_not_the_password():
    h = auth.hash_pw("a-good-password")
    assert "a-good-password" not in h and auth.check_pw("a-good-password", h) and not auth.check_pw("wrong", h)


def test_login_session_logout(user):
    cookie, age = auth.login("KemmaChat ", "a-good-password", "1.2.3.4", "Mozilla/5.0 (Macintosh)", True)
    s = auth.session_from_cookie(cookie)
    assert s and s["username"] == "kemmachat"
    assert auth.session_from_cookie(cookie + "x") is None
    auth.logout(cookie)
    assert auth.session_from_cookie(cookie) is None


def test_lockout_after_five_wrong(user):
    for _ in range(5):
        with pytest.raises(ValueError):
            auth.login("kemmachat", "wrong-password", "9.9.9.9", "ua", False)
    with pytest.raises(PermissionError):
        auth.login("kemmachat", "a-good-password", "9.9.9.9", "ua", False)
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE event='login' AND critical=1")["n"] == 1


def test_email_username_and_single_login(clean):
    db.run("DELETE FROM users")
    auth.create_user("WKemmachat@gmail.com", "a-good-password")
    assert db.one("SELECT username FROM users")["username"] == "wkemmachat@gmail.com"
    with pytest.raises(ValueError):
        auth.create_user("someone.else", "another-password")
    with pytest.raises(ValueError):
        auth.validate_new("has space", "a-good-password")
