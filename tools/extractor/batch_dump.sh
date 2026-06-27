#!/bin/bash
# batch_dump.sh — batch-dump asset paths through the CUE4Parse extractor.
#
# Usage:  batch_dump.sh <paths.txt> <category_name> [chunk_size]
#
# Reads one asset path per line from <paths.txt>, splits into chunks of
# ~80 paths/call (Windows command-line argument-length limit), runs the
# extractor's `dump` mode on each chunk, then moves matching JSON outputs
# from out/ into out/catalog/<category>/.
#
# Used by the game-map pipeline — see docs/game-map.md.

INPUT="$1"
CAT="$2"
CHUNK="${3:-80}"

if [ -z "$INPUT" ] || [ -z "$CAT" ]; then
  echo "usage: batch_dump.sh <paths.txt> <category> [chunk_size]"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUTROOT="$REPO_ROOT/tools/extractor/out"
EXTRACTOR="$REPO_ROOT/tools/extractor/extractor"

mkdir -p "$OUTROOT/catalog/$CAT"
total=$(wc -l < "$INPUT")
done=0
fails=0
start=$(date +%s)

cd "$EXTRACTOR"
split -l "$CHUNK" "$INPUT" /tmp/batch_chunk_
for chunk in /tmp/batch_chunk_*; do
  paths=$(tr '\n' ' ' < "$chunk")
  result=$("/c/Program Files/dotnet/dotnet.exe" run -c Release -- dump $paths 2>&1)
  ok=$(echo "$result" | grep -c "^OK ")
  fail=$(echo "$result" | grep -c "^FAIL ")
  done=$((done + ok))
  fails=$((fails + fail))
  elapsed=$(($(date +%s) - start))
  printf "  [%s] %d/%d done (%d fails) %ds\n" "$CAT" "$done" "$total" "$fails" "$elapsed"
done
rm -f /tmp/batch_chunk_*

mv_count=0
while IFS= read -r path; do
  name=$(basename "$path")
  if [ -f "$OUTROOT/$name.json" ]; then
    mv "$OUTROOT/$name.json" "$OUTROOT/catalog/$CAT/"
    mv_count=$((mv_count+1))
  fi
done < "$INPUT"
echo "  [$CAT] moved $mv_count JSONs into catalog/$CAT/"
