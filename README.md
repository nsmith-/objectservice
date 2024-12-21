Setting up dev env:
```bash
python3 -m venv .devenv
. .devenv/bin/activate
pip install -r dev-venv.txt
```

Testing on MiniKube:
```bash
./scripts/test-local.sh
```

Usernames for test environment:

| User         | Password | Role                |
|--------------|----------|---------------------|
| test_admin   | admin    | Administrative roles|
| test_readonly| bookworm | A read-only user    |
