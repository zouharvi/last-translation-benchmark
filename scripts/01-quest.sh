# push to remote
rsync -azP --filter=":- .gitignore" --exclude .git/ . ltb:/home/zouhar/last-translation-benchmark/

python3 server --host-public "https://last-translation-benchmark.vilda.net" --host "0.0.0.0" --port 80