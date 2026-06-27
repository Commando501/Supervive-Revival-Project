#!/bin/bash
# art_dump_all.sh — batch-dump every art/media asset category through the extractor.
# Drains ~75k assets across textures/meshes/materials/audio/animations/VFX into
# tools/extractor/out/catalog/<category>/ with progress logging to stdout.
#
# Designed to be run in background — total wall time on a fast machine ~2-3 hours.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO_ROOT/tools/extractor/out"
ALLFILES="$OUT/allfiles.txt"
BATCH="$REPO_ROOT/tools/extractor/batch_dump.sh"

# Order: small/fast categories first (quick wins), big ones last.
# (category_name regex_for_filename) pairs.
declare -a CATS=(
  "vfx        ^VFX_"
  "sc         ^SC_"
  "sb         ^SB_"
  "fx         ^FX_"
  "skel       ^SKEL_"
  "bs         ^BS_"
  "abp        ^ABP_"
  "spr        ^SPR_"
  "mf         ^MF_"
  "tex        ^Tex_"
  "comp       ^Comp_"
  "ps         ^PS_"
  "sk         ^SK_"
  "gie        ^GIE_"
  "lt         ^LT_"
  "snd        ^snd_"
  "en_voice   ^en_"
  "am         ^AM_"
  "gc         ^GC_"
  "wbp        ^WBP_"
  "tx         ^TX_"
  "anim       ^A_"
  "sfx        ^sfx_"
  "vo         ^vo_"
  "mat        ^M_"
  "ns         ^NS_"
  "sm         ^SM_"
  "mi         ^MI_"
  "tex_t      ^T_"
)

TOTAL_START=$(date +%s)
GRAND_OK=0
GRAND_FAIL=0

for entry in "${CATS[@]}"; do
  cat=$(echo "$entry" | awk '{print $1}')
  pat=$(echo "$entry" | awk '{print $2}')
  list="/tmp/art_${cat}.txt"
  awk -F/ -v p="$pat" '$NF ~ p' "$ALLFILES" | grep "\.uasset$" | sed 's/\.uasset$//' > "$list"
  n=$(wc -l < "$list")
  if [ "$n" -eq 0 ]; then
    printf "  [SKIP %s] no files matched %s\n" "$cat" "$pat"
    continue
  fi
  printf "\n===== %s : %d files =====\n" "$cat" "$n"
  bash "$BATCH" "$list" "$cat" 80
done

TOTAL_END=$(date +%s)
printf "\n===== ALL ART DUMPS COMPLETE in %d seconds =====\n" "$((TOTAL_END - TOTAL_START))"
ls -la "$OUT/catalog/" | head -50
