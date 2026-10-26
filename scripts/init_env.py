from pathlib import Path
import secrets

path = Path(".env")
if not path.exists():
    content = Path(".env.example").read_text().replace("replace-with-at-least-32-random-characters", secrets.token_urlsafe(48))
    with path.open("x") as output:
        output.write(content)
    path.chmod(0o600)
    print("Created .env with random session secret")
else:
    print("Kept existing .env unchanged")
