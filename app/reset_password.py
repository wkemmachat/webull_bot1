"""Reset the login from the bot's computer:  python -m app.reset_password [username]

The bot has one login. This sets its username and password (creating it if none exists yet)
and signs out every device. Run it on the Mac in the project folder, or on the server with
  docker compose exec bot python -m app.reset_password"""
import getpass
import sys
import time

from . import auth, db


def main():
    db.init()
    cur = db.one("SELECT id, username FROM users ORDER BY id LIMIT 1")
    default = cur["username"] if cur else ""
    name = sys.argv[1] if len(sys.argv) > 1 else input(f"Username{' [' + default + ']' if default else ''}: ")
    name = (name.strip() or default).lower()
    pw = getpass.getpass("New password (10+ characters): ")
    if pw != getpass.getpass("Repeat: "):
        print("The passwords are not the same.")
        return 1
    try:
        auth.validate_new(name, pw)
        if cur:
            with db.tx() as c:
                c.execute("UPDATE users SET username=?, pw_hash=?, pw_changed_at=? WHERE id=?",
                          (name, auth.hash_pw(pw), int(time.time()), cur["id"]))
                c.execute("DELETE FROM users WHERE id<>?", (cur["id"],))
                c.execute("UPDATE sessions SET revoked=1")
        else:
            auth.create_user(name, pw)
    except ValueError as e:
        print(e)
        return 1
    db.run("DELETE FROM login_attempts")
    print(f"Login set: '{name}'. All devices were signed out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
