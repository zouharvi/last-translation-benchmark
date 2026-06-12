# push to remote
rsync -azP --filter=":- .gitignore" --exclude .git/ . ltb:/home/zouhar/last-translation-benchmark/

# pull db from remote
rsync -azP ltb:/home/zouhar/last-translation-benchmark/data/db.sqlite data/
rsync -azP ltb:/home/zouhar/submissions.json data/

python3 server --host-public "https://last-translation-benchmark.vilda.net" --host "0.0.0.0" --port 80

# extract users and pull
ssh ltb "cd last-translation-benchmark; python3 scripts/02b-extract_submissions.py --output ~/submissions.json" && rsync -azP ltb:/home/zouhar/submissions.json data/
ssh ltb "cd last-translation-benchmark; python3 scripts/02c-extract_users.py --output ~/users.json" && rsync -azP ltb:/home/zouhar/users.json data/